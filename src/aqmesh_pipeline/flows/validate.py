"""Validate the raw JSON store against the bundled JSON Schemas.

This is a non-blocking pipeline step: schema violations are logged at ERROR
level but the flow always returns normally so a downstream clean step is
never aborted.  It can also be run standalone via ``aqmesh validate``.
"""

from __future__ import annotations

from prefect import flow, get_run_logger, task

from aqmesh_client.models import Param

from ..config import Settings, get_settings
from ..storage import raw_param_dir
from ..validate import load_schema, validate_raw_file


@task(name="validate-location-param")
def validate_location_param(settings: Settings, location_number: int, param: Param) -> dict:
    """Validate the most recent raw file for one (location, param) pair.

    Returns a result dict with keys ``location``, ``param``, ``status``
    (``"ok"`` | ``"invalid"`` | ``"skipped"``), and ``error_count``.
    """
    logger = get_run_logger()
    param_dir = raw_param_dir(settings, location_number, param)
    raw_files = sorted(param_dir.glob("*.json"))
    base = {"location": location_number, "param": param.label, "error_count": 0}

    if not raw_files:
        logger.debug("Location %s %s: no raw files — skipping.", location_number, param.label)
        return {**base, "status": "skipped"}

    latest = raw_files[-1]
    schema = load_schema(param)
    errors = validate_raw_file(latest, schema)

    if errors:
        for err in errors:
            logger.error(
                "Location %s %s — %s record %d: %s",
                location_number,
                param.label,
                latest.name,
                err["record_index"],
                err["message"],
            )
        return {**base, "file": latest.name, "status": "invalid", "error_count": len(errors)}

    logger.info("Location %s %s — %s: OK", location_number, param.label, latest.name)
    return {**base, "file": latest.name, "status": "ok"}


@flow(name="aqmesh-validate-raw")
def validate_raw_store(
    settings: Settings | None = None,
    summaries: list[dict] | None = None,
) -> dict:
    """Validate the most recent raw file per (location, param).

    When *summaries* is provided (from a preceding ingest run), only pairs
    with ``new_readings > 0`` and ``status == "ok"`` are checked.  When called
    standalone (``aqmesh validate``), every (location, param) directory with
    at least one file is validated.

    Always returns a report dict — never raises on schema violations.
    """
    settings = settings or get_settings()
    logger = get_run_logger()

    if summaries is not None:
        pairs: list[tuple[int, Param]] = [
            (s["location_number"], Param[s["param"].upper()])
            for s in summaries
            if s.get("new_readings", 0) > 0 and s.get("status") == "ok"
        ]
    else:
        pairs = []
        for loc_dir in sorted(settings.raw_dir.glob("location=*")):
            try:
                location_number = int(loc_dir.name.split("=", 1)[1])
            except (IndexError, ValueError):
                continue
            for param in Param:
                param_dir = loc_dir / f"param={param.label}"
                if param_dir.is_dir() and any(param_dir.glob("*.json")):
                    pairs.append((location_number, param))

    if not pairs:
        logger.info("No raw files to validate.")
        return {"checked": 0, "valid": 0, "invalid": 0, "invalid_files": []}

    results = [
        validate_location_param(settings, location_number, param)
        for location_number, param in pairs
    ]

    valid = [r for r in results if r["status"] == "ok"]
    invalid = [r for r in results if r["status"] == "invalid"]
    checked = len(valid) + len(invalid)

    if invalid:
        logger.error(
            "Validation: %d/%d file(s) failed — possible API schema drift.",
            len(invalid),
            checked,
        )
    else:
        logger.info("Validation: %d file(s) checked, all valid.", checked)

    return {
        "checked": checked,
        "valid": len(valid),
        "invalid": len(invalid),
        "invalid_files": invalid,
    }
