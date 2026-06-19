"""Cleaning flow: turn the raw store into research-ready CSV per location.

Reads all raw readings for each location (deduping rebased values), applies
sentinel handling + calibration via :mod:`aqmesh_pipeline.transform`, and writes
one CSV per location/param under ``clean/``.
"""

from __future__ import annotations

from prefect import flow, get_run_logger, task

from ..config import Settings, get_settings
from ..models import Param
from ..storage import clean_csv_path, read_raw_readings, write_clean_csv
from ..transform import clean_readings


@task(retries=2, retry_delay_seconds=10)
def clean_location_param(settings: Settings, location_number: int, param: Param) -> dict:
    """Clean one location/param and write its CSV. No-op if there is no raw data."""
    raw = read_raw_readings(settings, location_number, param)
    if raw.empty:
        return {"location_number": location_number, "param": param.label, "rows": 0, "csv": None}
    cleaned = clean_readings(raw, param)
    path = clean_csv_path(settings, location_number, param)
    write_clean_csv(cleaned, path)
    return {
        "location_number": location_number,
        "param": param.label,
        "rows": len(cleaned),
        "csv": str(path),
    }


@flow(name="aqmesh-clean")
def clean_data(settings: Settings | None = None) -> list[dict]:
    """Clean every location present in the raw store."""
    settings = settings or get_settings()
    logger = get_run_logger()
    results: list[dict] = []

    logger.info("raw_dir: %s (exists=%s)", settings.raw_dir, settings.raw_dir.exists())
    if not settings.raw_dir.exists():
        logger.warning("raw_dir does not exist — has ingest run successfully yet?")
        logger.info("Clean complete: wrote 0 CSV file(s).")
        return results

    for loc_dir in sorted(settings.raw_dir.glob("location=*")):
        location_number = int(loc_dir.name.split("=", 1)[1])
        for param in (Param.GAS, Param.PARTICLE):
            results.append(clean_location_param(settings, location_number, param))

    written = sum(1 for r in results if r["csv"])
    logger.info("Clean complete: wrote %d CSV file(s).", written)
    return results
