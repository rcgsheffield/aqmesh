"""Persist pipeline warnings/errors to the shared volume as serialised JSON.

Rather than hand-writing diagnostic records at each failure site (the approach
retired with issue #134), this module adds a single *logging route*: a
JSON-serialising rotating file handler attached to the logging hierarchy. Every
WARNING/ERROR emitted anywhere in the pipeline — including the API-error response
bodies now folded into those log messages — is captured automatically and lands
in ``logs/pipeline.jsonl`` under the shared data volume, with no per-site code.

The handler is attached to both the ``prefect`` and ``aqmesh_pipeline`` loggers:
flow/task code logs via Prefect's ``get_run_logger()`` (the ``prefect.*`` tree),
while library modules log via ``logging.getLogger(__name__)`` (the
``aqmesh_pipeline.*`` tree). Attaching directly to those two parents captures
both regardless of whether Prefect propagates to the root logger.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from .config import Settings

# Standard LogRecord attributes — everything else on a record is caller-supplied
# ``extra`` and worth serialising alongside the message.
_STANDARD_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

LOG_FILENAME = "pipeline.jsonl"
# Sentinel marking handlers this module owns, so reconfiguration can find and
# replace them without disturbing Prefect's or anyone else's handlers.
_HANDLER_MARKER = "_aqmesh_persisted"
# Loggers whose subtrees we persist: Prefect run loggers + our own library loggers.
_TARGET_LOGGERS = ("prefect", "aqmesh_pipeline")

logger = logging.getLogger(__name__)


class JsonLogFormatter(logging.Formatter):
    """Serialise a log record to a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        # Merge any caller-supplied extras (e.g. structured failure fields).
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and key not in payload:
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    value = repr(value)
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def _remove_existing_handlers() -> None:
    """Detach and close any handler this module previously attached."""
    for name in _TARGET_LOGGERS:
        log = logging.getLogger(name)
        for handler in [h for h in log.handlers if getattr(h, _HANDLER_MARKER, False)]:
            log.removeHandler(handler)
            handler.close()


def configure_persisted_logging(
    settings: Settings,
    *,
    max_bytes: int = 1_000_000,
    backup_count: int = 5,
) -> None:
    """Attach a rotating JSON file handler that persists WARNING+ logs.

    Idempotent: replaces any handler previously attached by this module, so
    repeated calls (e.g. the long-lived worker running ``pipeline`` each hour, or
    ``aqmesh pipeline`` configuring both the CLI and the flow) never stack
    handlers. Never raises — a filesystem failure is logged to the console and the
    run continues, mirroring the pipeline's "diagnostics must not abort" stance.

    Args:
        settings: Active settings; the file is written under ``settings.log_dir``.
        max_bytes: Rotate once the file exceeds this size.
        backup_count: Number of rotated backups to retain.
    """
    _remove_existing_handlers()
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            settings.log_dir / LOG_FILENAME,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Could not open persisted log file; continuing without it.", exc_info=True)
        return
    handler.setLevel(logging.WARNING)
    handler.setFormatter(JsonLogFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    for name in _TARGET_LOGGERS:
        logging.getLogger(name).addHandler(handler)
