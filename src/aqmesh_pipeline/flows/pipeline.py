"""Parent flow: ingest raw data then clean it. This is the scheduled entrypoint."""

from __future__ import annotations

from prefect import flow, get_run_logger

from ..config import get_settings
from ..storage import write_data_docs
from .clean import clean_data
from .ingest import ingest_raw
from .metadata import sync_location_metadata


@flow(name="aqmesh-pipeline")
def pipeline(resample: bool = True) -> dict:
    """Run the full pipeline: sync metadata, download raw readings, then produce cleaned CSVs.

    When ``resample`` is true (the default), the clean step also writes daily-resampled
    CSVs under ``resampled/``.
    """
    logger = get_run_logger()
    write_data_docs(get_settings())
    try:
        sync_location_metadata()
    except Exception:
        logger.warning("Metadata sync failed — continuing with ingest.")
    ingest_summary = ingest_raw()
    clean_results = clean_data(resample=resample)
    logger.info("Pipeline finished.")
    return {"ingest": ingest_summary, "clean": clean_results}
