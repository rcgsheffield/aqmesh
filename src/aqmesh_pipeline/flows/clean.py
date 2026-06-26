"""Cleaning flow: turn the raw store into research-ready CSV per location.

Reads all raw readings for each location (deduping rebased values), applies
sentinel handling + calibration via :mod:`aqmesh_pipeline.transform`, and writes
one CSV per location/param under ``clean/``. By default it also writes a daily
resampled CSV per location/param under ``resampled/``.
"""

from __future__ import annotations

from prefect import flow, get_run_logger, task

from ..config import Settings, get_settings
from ..models import Param
from ..storage import (
    clean_csv_path,
    read_raw_readings,
    resampled_csv_path,
    write_clean_csv,
)
from ..transform import clean_readings, resample_daily


@task(retries=2, retry_delay_seconds=10)
def clean_location_param(
    settings: Settings, location_number: int, param: Param, resample: bool = True
) -> dict:
    """Clean one location/param and write its CSV. No-op if there is no raw data.

    When ``resample`` is true, also writes a daily resampled CSV under the
    separate ``resampled/`` tree.
    """
    raw = read_raw_readings(settings, location_number, param)
    if raw.empty:
        return {
            "location_number": location_number,
            "param": param.label,
            "rows": 0,
            "csv": None,
            "resampled_csv": None,
        }
    cleaned = clean_readings(raw, param)
    path = clean_csv_path(settings, location_number, param)
    write_clean_csv(cleaned, path)

    resampled_path = None
    if resample:
        resampled_path = resampled_csv_path(settings, location_number, param)
        write_clean_csv(resample_daily(cleaned), resampled_path)

    return {
        "location_number": location_number,
        "param": param.label,
        "rows": len(cleaned),
        "csv": str(path),
        "resampled_csv": str(resampled_path) if resampled_path else None,
    }


@flow(name="aqmesh-clean")
def clean_data(settings: Settings | None = None, resample: bool = True) -> list[dict]:
    """Clean every location present in the raw store.

    When ``resample`` is true (the default), a daily resampled CSV is also
    written under ``resampled/`` for each location/param.
    """
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
            results.append(clean_location_param(settings, location_number, param, resample))

    written = sum(1 for r in results if r["csv"])
    resampled_written = sum(1 for r in results if r["resampled_csv"])
    logger.info(
        "Clean complete: wrote %d CSV file(s) and %d resampled file(s).",
        written,
        resampled_written,
    )
    return results
