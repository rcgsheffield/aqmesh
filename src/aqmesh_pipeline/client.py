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
from .models import Asset, FailedSensor, Param, SensorDetail, ServerPing

logger = logging.getLogger(__name__)

# Tokens are valid for 120 minutes (manual 3.1); refresh a little early.
TOKEN_LIFETIME_SECONDS = 120 * 60
TOKEN_REFRESH_BUFFER_SECONDS = 5 * 60

# Truncation cap for a logged error body — long enough to capture a useful
# vendor diagnostic, short enough not to flood the logs with a huge payload.
MAX_BODY_CHARS = 2000


class AQMeshAuthError(RuntimeError):
    """Authentication with the AQMesh API failed."""


def http_error_body(exc: BaseException, *, limit: int = MAX_BODY_CHARS) -> str | None:
    """Return the response body for an httpx error, truncated to ``limit`` chars.

    ``str(exc)`` for an ``httpx.HTTPStatusError`` gives the status and URL but not
    the response body — the vendor error message or 500 detail that explains the
    failure. This pulls that body out so callers can log it alongside the status.

    Returns ``None`` when there is no readable response — e.g. an
    ``httpx.TransportError`` (timeout/connection failure) carries no ``.response``,
    or ``.text`` is itself undecodable. Never raises.
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    try:
        return resp.text[:limit]
    except Exception:
        return None


class AQMeshClient:
    """A thin, retrying wrapper around the AQMesh REST API."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        """Initialise the client with credentials and connection settings.

        Args:
            settings: Pipeline configuration including API credentials and base URL.
            client: Optional pre-built httpx client (injected in tests).
        """
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
        """Close the underlying HTTP connection pool."""
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
    def _get(self, path: str, *, authenticated: bool = True) -> httpx.Response:
        """GET ``path``, retrying transient errors and (when authenticated) re-authing on 401.

        Args:
            path: API path relative to the base URL.
            authenticated: Send a bearer token and refresh it once on 401. Set False
                for public endpoints such as ``/serverping`` (manual 4.16) so the call
                still works when credentials are absent or expired.
        """
        last_exc: Exception | None = None
        reauthed = False
        for attempt in range(self._settings.max_retries + 1):
            headers = {}
            if authenticated:
                headers["Authorization"] = f"Bearer {self.authenticate()}"
            try:
                resp = self._client.get(path, headers=headers)
            except httpx.TransportError as exc:  # network/timeout
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if authenticated and resp.status_code == httpx.codes.UNAUTHORIZED and not reauthed:
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
        """Sleep for an exponentially increasing delay, capped at 30 seconds.

        Args:
            attempt: Zero-based retry attempt number.
        """
        time.sleep(min(2**attempt, 30))

    # -- API calls -------------------------------------------------------
    def get_assets(self) -> list[Asset]:
        """Return all pods/locations available to the authenticated user."""
        resp = self._get("/Pods/Assets_V1")
        return [Asset.model_validate(item) for item in resp.json()]

    # -- diagnostics / context (read-only) -------------------------------
    def server_ping(self) -> ServerPing:
        """Return the server health snapshot (manual 4.16).

        Requires no authentication, so it works as a liveness probe even when
        credentials are missing or expired.
        """
        resp = self._get("/serverping", authenticated=False)
        return ServerPing.model_validate(resp.json())

    def get_system_notifications(self) -> list[str]:
        """Return operator notices, e.g. planned downtime announcements (manual 4.17)."""
        resp = self._get("/notification/system")
        if resp.status_code == httpx.codes.NO_CONTENT or not resp.content:
            return []
        return [
            item["system_information"] for item in resp.json() if item.get("system_information")
        ]

    def get_failed_sensors(self) -> list[FailedSensor]:
        """Return sensors that have tripped their fail criteria (manual 4.8)."""
        resp = self._get("/Pods/SensorFail")
        if resp.status_code == httpx.codes.NO_CONTENT or not resp.content:
            return []
        return [FailedSensor.model_validate(item) for item in resp.json()]

    def get_sensor_details(self, *, active: bool = False) -> list[SensorDetail]:
        """Return per-sensor status, age, and expiry for deployed pods (manual 4.20).

        Args:
            active: Restrict to active/installed pods (the manual's ``Active=1``
                filter). When False (default), include all deployed pods.
        """
        # The manual documents a literal double slash before the Active flag, but that
        # 404s in production; a single slash returns 401 (ownership-scoped, not a
        # missing route) instead — see issue #121 and docs/api-reference/diagnostics.md.
        resp = self._get(f"/sensor/SensorDetail/{1 if active else 0}")
        if resp.status_code == httpx.codes.NO_CONTENT or not resp.content:
            return []
        return [SensorDetail.model_validate(item) for item in resp.json()]

    def iter_location_data(self, location_number: int, param: Param) -> Iterator[list[dict]]:
        """Yield successive reading batches for a location until the cursor is exhausted.

        Each call to the ``Next`` endpoint advances a server-side pointer, so we loop
        until the server returns no more readings (HTTP 204 or an empty array).
        """
        s = self._settings
        while True:
            # The route rejects a trailing /{version} segment (even /0); the manual's
            # worked examples all use 4 segments, so only append version when non-default.
            path = f"/LocationData/Next/{location_number}/{int(param)}/{s.units}/{s.tpc}"
            if s.version:
                path += f"/{s.version}"
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

    def repeat_last(self, location_number: int, param: Param) -> list[dict]:
        """Re-fetch the most recently delivered batch without advancing the cursor (manual 4.11).

        Calls ``/LocationData/Repeat`` which returns the same data as the most recent
        ``/LocationData/Next`` response. The server-side pointer is not advanced.
        Returns an empty list when there is no previous batch (HTTP 204 or empty body).

        Note: the Repeat endpoint has no TPC segment, unlike Next.
        """
        s = self._settings
        path = f"/LocationData/Repeat/{location_number}/{int(param)}/{s.units}"
        if s.version:
            path += f"/{s.version}"
        resp = self._get(path)
        if resp.status_code == httpx.codes.NO_CONTENT or not resp.content:
            return []
        return resp.json() or []
