"""Parent flow: ingest raw data then clean it. This is the scheduled entrypoint."""

from __future__ import annotations

from prefect import flow, get_run_logger

from .clean import clean_data
from .ingest import ingest_raw


@flow(name="aqmesh-pipeline")
def pipeline(resample: bool = True) -> dict:
    """Run the full pipeline: download raw readings, then produce cleaned CSVs.

    When ``resample`` is true (the default), the clean step also writes 5-minute
    resampled CSVs under ``resampled/``.
    """
    logger = get_run_logger()
    ingest_summary = ingest_raw()
    clean_results = clean_data(resample=resample)
    logger.info("Pipeline finished.")
    return {"ingest": ingest_summary, "clean": clean_results}
