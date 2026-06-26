"""Ingestion flow: download all available raw readings to the shared volume.

Follows the manual's data-access workflow (section 3): authenticate, list assets,
then for each location loop the cursor-style ``Next`` endpoint until exhausted.
Every batch is written to the raw store immediately so an interruption mid-loop
never loses already-fetched (and already-advanced) readings.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE

from ..client import AQMeshClient
from ..config import Settings, get_settings
from ..metadata import build_raw_store_descriptor
from ..models import READING_DATESTAMP_FIELD, Param
from ..storage import (
    load_pointers,
    raw_store_descriptor_path,
    save_assets,
    save_pointers,
    update_pointer,
    write_raw_batch,
    write_raw_store_descriptor,
)


@task(retries=3, retry_delay_seconds=30, cache_policy=NO_CACHE)
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

    try:
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
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
            logger.warning(
                "Location %s %s: not found (HTTP 404) — pod may not be deployed yet.",
                location_number,
                param.label,
            )
            return {
                "location_number": location_number,
                "param": param.label,
                "new_readings": total,
                "last_reading_number": max_reading_number,
                "last_datestamp": last_datestamp,
                "status": "not_found",
            }
        # The vendor API returns a persistent 500 for some params (issue #9). The
        # client has already exhausted its retries, so isolate this param's failure
        # here: log it and return a "failed" summary rather than letting it abort the
        # whole run, so the other params and locations still flow.
        logger.error(
            "Location %s %s: fetch failed after retries (%s) -- skipping this param.",
            location_number,
            param.label,
            exc,
        )
        return {
            "location_number": location_number,
            "param": param.label,
            "new_readings": total,
            "last_reading_number": max_reading_number,
            "last_datestamp": last_datestamp,
            "status": "failed",
            "error": str(exc),
        }

    logger.info("Location %s %s: %d new readings.", location_number, param.label, total)
    return {
        "location_number": location_number,
        "param": param.label,
        "new_readings": total,
        "last_reading_number": max_reading_number,
        "last_datestamp": last_datestamp,
        "status": "ok",
    }


@flow(name="aqmesh-ingest-raw")
def ingest_raw(settings: Settings | None = None) -> dict:
    """Download raw data for every location available to the user."""
    settings = settings or get_settings()
    logger = get_run_logger()
    pulled_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pointers = load_pointers(settings)
    summaries: list[dict] = []

    logger.info("environment: %s  base_url: %s", settings.environment, settings.base_url)
    logger.info("data_root: %s", settings.data_root)

    with AQMeshClient(settings) as client:
        client.authenticate()
        assets = client.get_assets()
        # Snapshot the assets so the offline clean stage can read location provenance.
        save_assets(settings, assets)
        logger.info("Discovered %d locations.", len(assets))
        if not assets:
            logger.warning("No locations returned by the API — check environment/credentials.")
        for asset in assets:
            for param in list(Param):
                summary = ingest_location_param(
                    client, settings, asset.location_number, param, pulled_at
                )
                summaries.append(summary)
                # Only advance the pointer on success, so a failed poll preserves the
                # last known-good progress rather than clobbering it.
                if summary["status"] == "ok":
                    update_pointer(
                        pointers,
                        asset.location_number,
                        param,
                        last_reading_number=summary["last_reading_number"],
                        last_datestamp=summary["last_datestamp"],
                        new_readings=summary["new_readings"],
                    )

    save_pointers(settings, pointers)

    try:
        descriptor = build_raw_store_descriptor(
            assets={a.location_number: a for a in assets},
            pointers=pointers,
            summaries=summaries,
            settings=settings,
            generated_at=datetime.now(UTC),
        )
        write_raw_store_descriptor(descriptor, raw_store_descriptor_path(settings))
    except Exception:
        logger.warning("Failed to write raw store descriptor; skipping.", exc_info=True)

    total_new = sum(s["new_readings"] for s in summaries)
    failed = [s for s in summaries if s["status"] == "failed"]
    not_found = [s for s in summaries if s["status"] == "not_found"]
    if not_found:
        logger.warning(
            "%d location/param(s) not found (HTTP 404): %s",
            len(not_found),
            ", ".join(f"{s['location_number']}/{s['param']}" for s in not_found),
        )
    if failed:
        logger.warning(
            "%d location/param fetch(es) failed: %s",
            len(failed),
            ", ".join(f"{s['location_number']}/{s['param']}" for s in failed),
        )
    logger.info("Ingest complete: %d new readings across %d locations.", total_new, len(assets))
    return {"pulled_at": pulled_at, "locations": len(assets), "summaries": summaries}
