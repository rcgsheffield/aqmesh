"""Tests for the API-error diagnostics capture module (issue #134)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from aqmesh_pipeline.diagnostics import (
    diagnostics_path,
    http_error_body,
    record_api_error,
)


def _status_error(status_code: int, body: str) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError with a response, mirroring client._get()."""
    request = httpx.Request("GET", "https://example.test/LocationData/Next/510/1/01/1")
    response = httpx.Response(status_code, text=body, request=request)
    return httpx.HTTPStatusError(f"server error {status_code}", request=request, response=response)


def test_record_api_error_persists_status_and_body(settings):
    exc = _status_error(500, "boom")
    when = datetime(2026, 7, 7, 6, 0, 0, tzinfo=UTC)

    record = record_api_error(
        settings,
        context={"stage": "ingest", "location_number": 510, "param": "gas"},
        exc=exc,
        when=when,
    )

    # Returned record carries the captured detail...
    assert record["status_code"] == 500
    assert record["response_body"] == "boom"
    assert record["error_type"] == "HTTPStatusError"
    assert record["stage"] == "ingest"
    assert record["location_number"] == 510
    assert record["param"] == "gas"
    assert record["timestamp"] == "2026-07-07T06:00:00+00:00"

    # ...and the same record is appended to diagnostics.jsonl as one JSON line.
    lines = diagnostics_path(settings).read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record


def test_record_api_error_appends_without_overwriting(settings):
    record_api_error(settings, context={"stage": "ingest"}, exc=_status_error(500, "one"))
    record_api_error(settings, context={"stage": "metadata"}, exc=_status_error(404, "two"))

    lines = diagnostics_path(settings).read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["response_body"] for line in lines] == ["one", "two"]


def test_http_error_body_none_for_transport_error():
    """TransportError (timeout/connection) carries no response — body is None."""
    exc = httpx.ConnectTimeout("timed out")
    assert http_error_body(exc) is None


def test_record_api_error_records_non_http_exception(settings):
    """A non-httpx exception is still recorded (with no status/body)."""
    record = record_api_error(settings, context={"stage": "metadata"}, exc=ValueError("weird"))
    assert record["status_code"] is None
    assert record["response_body"] is None
    assert record["error_type"] == "ValueError"
    assert record["error"] == "weird"


def test_http_error_body_truncates_to_limit():
    exc = _status_error(500, "x" * 5000)
    assert http_error_body(exc, limit=100) == "x" * 100


def test_record_api_error_never_raises_on_write_failure(settings, monkeypatch):
    """A diagnostics-write failure must not abort the caller."""

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.mkdir", _boom)

    # Must return the record rather than propagating the OSError.
    record = record_api_error(settings, context={"stage": "ingest"}, exc=_status_error(500, "b"))
    assert record["status_code"] == 500
    assert not diagnostics_path(settings).exists()
