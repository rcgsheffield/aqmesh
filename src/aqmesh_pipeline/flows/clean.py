"""Cleaning flow: turn the raw store into research-ready CSV per location.

Reads all raw readings for each location (deduping rebased values), applies
sentinel handling + calibration via :mod:`aqmesh_pipeline.transform`, and writes
one CSV per location/param under ``clean/``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from prefect import flow, get_run_logger, task

from ..config import Settings, get_settings
from ..metadata import build_metadata
from ..models import Asset, Param
from ..storage import (
    clean_csv_path,
    clean_metadata_path,
    load_assets,
    read_raw_readings,
    write_clean_csv,
    write_clean_metadata,
)
from ..transform import clean_readings


@task(retries=2, retry_delay_seconds=10)
def clean_location_param(
    settings: Settings, location_number: int, param: Param, asset: Asset | None = None
) -> dict:
    """Clean one location/param, write its CSV and metadata sidecar. No-op if no raw data."""
    raw = read_raw_readings(settings, location_number, param)
    if raw.empty:
        return {
            "location_number": location_number,
            "param": param.label,
            "rows": 0,
            "csv": None,
            "metadata": None,
        }
    cleaned = clean_readings(raw, param)
    path = clean_csv_path(settings, location_number, param)
    write_clean_csv(cleaned, path)

    metadata = build_metadata(cleaned, raw, param, asset, settings, datetime.now(UTC))
    meta_path = clean_metadata_path(settings, location_number, param)
    write_clean_metadata(metadata, meta_path)
    return {
        "location_number": location_number,
        "param": param.label,
        "rows": len(cleaned),
        "csv": str(path),
        "metadata": str(meta_path),
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

    assets = load_assets(settings)
    for loc_dir in sorted(settings.raw_dir.glob("location=*")):
        location_number = int(loc_dir.name.split("=", 1)[1])
        asset = assets.get(location_number)
        for param in (Param.GAS, Param.PARTICLE):
            results.append(clean_location_param(settings, location_number, param, asset))

    written = sum(1 for r in results if r["csv"])
    logger.info("Clean complete: wrote %d CSV file(s).", written)
    return results
