"""Tests for the persisted-log route (issue #134)."""

from __future__ import annotations

import json
import logging

import pytest

from aqmesh_pipeline.logging_setup import (
    _HANDLER_MARKER,
    _TARGET_LOGGERS,
    LOG_FILENAME,
    _remove_existing_handlers,
    configure_persisted_logging,
)


@pytest.fixture
def persisted_logging(settings):
    """Configure the persisted-log handler and tear it down after the test."""
    configure_persisted_logging(settings)
    log_file = settings.log_dir / LOG_FILENAME
    yield log_file
    _remove_existing_handlers()


def _marked_handlers(name: str) -> list[logging.Handler]:
    return [h for h in logging.getLogger(name).handlers if getattr(h, _HANDLER_MARKER, False)]


def _read_records(log_file) -> list[dict]:
    return [json.loads(line) for line in log_file.read_text().splitlines()]


def test_persists_warning_as_json(persisted_logging):
    logging.getLogger("aqmesh_pipeline.sometest").warning("body was %s", "boom")

    records = _read_records(persisted_logging)
    assert len(records) == 1
    assert records[0]["level"] == "WARNING"
    assert records[0]["message"] == "body was boom"
    assert records[0]["logger"] == "aqmesh_pipeline.sometest"
    assert "timestamp" in records[0]


def test_info_is_not_persisted(persisted_logging):
    """The handler's WARNING threshold drops INFO even when the logger allows it."""
    log = logging.getLogger("aqmesh_pipeline.sometest")
    log.setLevel(logging.DEBUG)
    log.info("routine chatter")

    assert not persisted_logging.exists() or _read_records(persisted_logging) == []


def test_exc_info_serialises_traceback(persisted_logging):
    try:
        raise ValueError("weird")
    except ValueError:
        logging.getLogger("aqmesh_pipeline.sometest").warning("failed", exc_info=True)

    records = _read_records(persisted_logging)
    assert len(records) == 1
    assert "ValueError: weird" in records[0]["traceback"]


def test_configuration_is_idempotent(settings):
    """Repeated calls (hourly worker, CLI + flow) must not stack handlers or dupe lines."""
    configure_persisted_logging(settings)
    configure_persisted_logging(settings)
    try:
        for name in _TARGET_LOGGERS:
            assert len(_marked_handlers(name)) == 1

        logging.getLogger("aqmesh_pipeline.sometest").warning("once")
        assert len(_read_records(settings.log_dir / LOG_FILENAME)) == 1
    finally:
        _remove_existing_handlers()


def test_rotating_handler_configured(persisted_logging, settings):
    handler = _marked_handlers("aqmesh_pipeline")[0]
    assert handler.maxBytes == 1_000_000
    assert handler.backupCount == 5
    assert handler.level == logging.WARNING
