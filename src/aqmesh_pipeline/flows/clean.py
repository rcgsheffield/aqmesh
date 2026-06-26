"""Cleaning flow: turn the raw store into research-ready CSV per location.

Reads all raw readings for each location (deduping rebased values), applies
sentinel handling + calibration via :mod:`aqmesh_pipeline.transform`, and writes
one CSV per location/param under ``clean/``. By default it also writes a daily
resampled CSV per location/param under ``resampled/``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from prefect import flow, get_run_logger, task

from ..config import Settings, get_settings
from ..csvw import build_csvw
from ..metadata import build_metadata
from ..models import Asset, Param
from ..storage import (
    assets_path,
    clean_csv_path,
    clean_csvw_path,
    clean_metadata_path,
    load_assets,
    read_raw_readings,
    resampled_csv_path,
    write_clean_csv,
    write_clean_csvw,
    write_clean_metadata,
)
from ..transform import clean_readings, resample_daily


@task(retries=2, retry_delay_seconds=10)
def clean_location_param(
    settings: Settings,
    location_number: int,
    param: Param,
    asset: Asset | None = None,
    resample: bool = True,
) -> dict:
    """Clean one location/param, write its CSV and metadata sidecar. No-op if no raw data.

    When ``resample`` is true (the default), also writes a daily resampled CSV under the
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
            "metadata": None,
            "csvw": None,
        }
    cleaned = clean_readings(raw, param)
    path = clean_csv_path(settings, location_number, param)
    write_clean_csv(cleaned, path)

    metadata = build_metadata(cleaned, raw, param, asset, settings, datetime.now(UTC))
    meta_path = clean_metadata_path(settings, location_number, param)
    write_clean_metadata(metadata, meta_path)

    csvw = build_csvw(metadata, path.name)
    csvw_path = clean_csvw_path(settings, location_number, param)
    write_clean_csvw(csvw, csvw_path)

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
        "metadata": str(meta_path),
        "csvw": str(csvw_path),
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

    assets = load_assets(settings)
    if not assets and assets_path(settings).exists():
        raise RuntimeError(
            "Asset registry (assets.json) exists but is empty — the API returned no pods. "
            "Check credentials and re-run the metadata/ingest stages."
        )
    if assets:
        location_numbers = sorted(assets.keys())
        logger.info("Processing %d location(s) from asset registry.", len(location_numbers))
    elif settings.raw_dir.exists():
        location_numbers = sorted(
            int(d.name.split("=", 1)[1]) for d in settings.raw_dir.glob("location=*")
        )
        logger.info(
            "No asset registry found; discovered %d location(s) from raw store.",
            len(location_numbers),
        )
    else:
        logger.warning("raw_dir does not exist and no asset registry found — has ingest run?")
        logger.info("Clean complete: wrote 0 CSV file(s).")
        return results

    for location_number in location_numbers:
        asset = assets.get(location_number)
        for param in (Param.GAS, Param.PARTICLE):
            results.append(clean_location_param(settings, location_number, param, asset, resample))

    written = sum(1 for r in results if r["csv"])
    resampled_written = sum(1 for r in results if r["resampled_csv"])
    logger.info(
        "Clean complete: wrote %d CSV file(s) and %d resampled file(s).",
        written,
        resampled_written,
    )
    return results
