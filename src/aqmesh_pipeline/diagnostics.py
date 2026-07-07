"""Persist API error response bodies for later debugging (issue #134).

When a pipeline run hits an API failure, ``str(exc)`` for an
``httpx.HTTPStatusError`` gives the status code and URL but *not* the response
body. That body — a vendor error message, malformed JSON, or a 500's diagnostic
detail — is the thing that tells you whether an incident is a new failure mode
or a repeat of a known one. This module captures it and appends a record to a
durable, append-only JSONL log under ``state/diagnostics.jsonl``.

Writing is append-only (never rewritten), following the raw store's
"never modified" philosophy rather than the atomic whole-file rewrites used for
mutable state such as ``pointers.json``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings

logger = logging.getLogger(__name__)

DIAGNOSTICS_FILENAME = "diagnostics.jsonl"
# Truncation cap for both the persisted body and the log line — long enough to
# capture a useful diagnostic, short enough to avoid flooding logs/state with a
# huge payload.
MAX_BODY_CHARS = 2000


def diagnostics_path(settings: Settings) -> Path:
    """Path to the append-only API-error diagnostics log."""
    return settings.state_dir / DIAGNOSTICS_FILENAME


def http_error_body(exc: BaseException, *, limit: int = MAX_BODY_CHARS) -> str | None:
    """Return the response body for an httpx error, truncated to ``limit`` chars.

    Returns ``None`` when there is no response to read — e.g. an
    ``httpx.TransportError`` (timeout/connection failure) carries no ``.response``.
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    try:
        return resp.text[:limit]
    except Exception:
        # Reading .text can itself fail (e.g. undecodable content); never let
        # diagnostics collection raise.
        return None


def record_api_error(
    settings: Settings,
    *,
    context: dict,
    exc: BaseException,
    when: datetime | None = None,
) -> dict:
    """Build a diagnostic record, append it to ``diagnostics.jsonl``, and return it.

    Never raises: a diagnostics-write failure must not abort the pipeline. The
    returned record lets callers reuse ``record["response_body"]`` in their log
    message without re-truncating.

    Args:
        settings: Active settings (used to locate the state directory).
        context: Caller-supplied fields identifying the failure site, e.g.
            ``{"stage": "ingest", "location_number": 510, "param": "gas"}``.
        exc: The exception that was caught. httpx errors contribute a status code
            and body; other exceptions are still recorded (with ``None`` for both).
        when: Timestamp override, primarily for tests. Defaults to now (UTC).
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    record = {
        "timestamp": (when or datetime.now(UTC)).isoformat(),
        **context,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "status_code": status,
        "response_body": http_error_body(exc),
    }
    try:
        path = diagnostics_path(settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:  # append-only, never rewritten
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning("Failed to persist API-error diagnostic.", exc_info=True)
    return record
