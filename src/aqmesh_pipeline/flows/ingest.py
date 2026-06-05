"""Ingestion flow: download all available raw readings to the shared volume.

Follows the manual's data-access workflow (section 3): authenticate, list assets,
then for each location loop the cursor-style ``Next`` endpoint until exhausted.
Every batch is written to the raw store immediately so an interruption mid-loop
never loses already-fetched (and already-advanced) readings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from prefect import flow, get_run_logger, task

from ..client import AQMeshClient
from ..config import Settings, get_settings
from ..models import READING_DATESTAMP_FIELD, Param
from ..storage import load_pointers, save_pointers, update_pointer, write_raw_batch


@task(retries=3, retry_delay_seconds=30)
def ingest_location_param(
    client: AQMeshClient,
    settings: Settings,
    location_number: int,
    param: Param,
    pulled_at: str,
) -> dict:
    """Download and persist every unread reading for one location/param."""
    logger = get_run_logger()
    max_reading_number: int | None = None
    last_datestamp: str | None = None
    total = 0

    for seq, batch in enumerate(client.iter_location_data(location_number, param)):
        write_raw_batch(settings, location_number, param, batch, pulled_at, seq)
        total += len(batch)
        for record in batch:
            rn = record.get(param.reading_number_field)
            if rn is not None and (max_reading_number is None or rn > max_reading_number):
                max_reading_number = rn
            ds = record.get(READING_DATESTAMP_FIELD)
            if ds and (last_datestamp is None or ds > last_datestamp):
                last_datestamp = ds

    logger.info(
        "Location %s %s: %d new readings.", location_number, param.label, total
    )
    return {
        "location_number": location_number,
        "param": param.label,
        "new_readings": total,
        "last_reading_number": max_reading_number,
        "last_datestamp": last_datestamp,
    }


@flow(name="aqmesh-ingest-raw")
def ingest_raw(settings: Settings | None = None) -> dict:
    """Download raw data for every location available to the user."""
    settings = settings or get_settings()
    logger = get_run_logger()
    pulled_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pointers = load_pointers(settings)
    summaries: list[dict] = []

    with AQMeshClient(settings) as client:
        client.authenticate()
        assets = client.get_assets()
        logger.info("Discovered %d locations.", len(assets))
        for asset in assets:
            for param in (Param.GAS, Param.PARTICLE):
                summary = ingest_location_param(
                    client, settings, asset.location_number, param, pulled_at
                )
                update_pointer(
                    pointers,
                    asset.location_number,
                    param,
                    last_reading_number=summary["last_reading_number"],
                    last_datestamp=summary["last_datestamp"],
                    new_readings=summary["new_readings"],
                )
                summaries.append(summary)

    save_pointers(settings, pointers)
    total_new = sum(s["new_readings"] for s in summaries)
    logger.info("Ingest complete: %d new readings across %d locations.", total_new, len(assets))
    return {"pulled_at": pulled_at, "locations": len(assets), "summaries": summaries}
