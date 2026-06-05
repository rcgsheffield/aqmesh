"""HTTP client for the AQMesh API.

Implements the three calls the pipeline needs (manual sections 4.1, 4.19, 4.10):

* :meth:`AQMeshClient.authenticate` - exchange credentials for a bearer token
  (valid 120 minutes; cached and refreshed automatically).
* :meth:`AQMeshClient.get_assets` - list the pods/locations available to the user.
* :meth:`AQMeshClient.iter_location_data` - the cursor-style "Next" loop that
  yields every unread reading batch for a location until the server is exhausted.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import httpx

from .config import Settings
from .models import Asset, Param

logger = logging.getLogger(__name__)

# Tokens are valid for 120 minutes (manual 3.1); refresh a little early.
TOKEN_LIFETIME_SECONDS = 120 * 60
TOKEN_REFRESH_BUFFER_SECONDS = 5 * 60


class AQMeshAuthError(RuntimeError):
    """Authentication with the AQMesh API failed."""


class AQMeshClient:
    """A thin, retrying wrapper around the AQMesh REST API."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.request_timeout,
            headers={"Accept": "application/json"},
        )
        self._token: str | None = None
        self._token_deadline: float = 0.0

    # -- context manager -------------------------------------------------
    def __enter__(self) -> AQMeshClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- authentication --------------------------------------------------
    def authenticate(self, *, force: bool = False) -> str:
        """Return a valid bearer token, fetching a new one if needed."""
        if not force and self._token and time.monotonic() < self._token_deadline:
            return self._token

        resp = self._client.post(
            "/Authenticate",
            json={
                "username": self._settings.username,
                "password": self._settings.password.get_secret_value(),
            },
        )
        if resp.status_code != httpx.codes.OK:
            raise AQMeshAuthError(
                f"Authenticate failed with HTTP {resp.status_code}: {resp.text[:200]}"
            )
        token = resp.json().get("token")
        if not token:
            raise AQMeshAuthError("Authenticate response did not contain a token.")

        self._token = token
        self._token_deadline = (
            time.monotonic() + TOKEN_LIFETIME_SECONDS - TOKEN_REFRESH_BUFFER_SECONDS
        )
        logger.info("Authenticated with AQMesh API (%s).", self._settings.environment)
        return token

    # -- core request with retry + re-auth -------------------------------
    def _get(self, path: str) -> httpx.Response:
        """GET ``path`` with bearer auth, retrying transient errors once-re-authing on 401."""
        last_exc: Exception | None = None
        reauthed = False
        for attempt in range(self._settings.max_retries + 1):
            token = self.authenticate()
            try:
                resp = self._client.get(path, headers={"Authorization": f"Bearer {token}"})
            except httpx.TransportError as exc:  # network/timeout
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code == httpx.codes.UNAUTHORIZED and not reauthed:
                # Token may have expired server-side; force one refresh and retry.
                reauthed = True
                self.authenticate(force=True)
                continue
            if resp.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
                last_exc = httpx.HTTPStatusError(
                    f"server error {resp.status_code}", request=resp.request, response=resp
                )
                self._sleep_backoff(attempt)
                continue

            resp.raise_for_status()
            return resp

        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2**attempt, 30))

    # -- API calls -------------------------------------------------------
    def get_assets(self) -> list[Asset]:
        """Return all pods/locations available to the authenticated user."""
        resp = self._get("/Pods/Assets_V1")
        return [Asset.model_validate(item) for item in resp.json()]

    def iter_location_data(
        self, location_number: int, param: Param
    ) -> Iterator[list[dict]]:
        """Yield successive reading batches for a location until the cursor is exhausted.

        Each call to the ``Next`` endpoint advances a server-side pointer, so we loop
        until the server returns no more readings (HTTP 204 or an empty array).
        """
        s = self._settings
        while True:
            path = (
                f"/LocationData/Next/{location_number}/{int(param)}"
                f"/{s.units}/{s.tpc}/{s.version}"
            )
            resp = self._get(path)
            if resp.status_code == httpx.codes.NO_CONTENT or not resp.content:
                return
            batch = resp.json()
            if not batch:
                return
            logger.debug(
                "Location %s %s: fetched %d readings.", location_number, param.label, len(batch)
            )
            yield batch
