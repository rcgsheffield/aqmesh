"""Metadata sync: fetch location and sensor metadata from the API.

Runs first in the pipeline so that every registered pod has a ``info.json``
sidecar under ``clean/location=<n>/`` — even pods that are not yet delivering
readings and would otherwise be invisible to the clean step.
"""

from __future__ import annotations

from collections import defaultdict

from prefect import flow, get_run_logger

from ..client import AQMeshClient
from ..config import Settings, get_settings
from ..storage import save_assets, write_location_info


@flow(name="aqmesh-sync-metadata")
def sync_location_metadata(settings: Settings | None = None) -> list[dict]:
    """Fetch all asset and sensor metadata from the API; write per-location info.json files."""
    settings = settings or get_settings()
    logger = get_run_logger()

    with AQMeshClient(settings) as client:
        client.authenticate()
        assets = client.get_assets()
        sensor_details = client.get_sensor_details()

    # Index sensor details by pod serial number for O(1) lookup.
    sensors_by_pod: dict[int, list[dict]] = defaultdict(list)
    for sd in sensor_details:
        if sd.serial_number is not None:
            sensors_by_pod[sd.serial_number].append(sd.model_dump())

    # Build enriched records: Asset fields + all sensors for that pod.
    records = []
    for asset in assets:
        record = asset.model_dump()
        record["sensors"] = sensors_by_pod.get(asset.serial_number, [])
        records.append(record)

    save_assets(settings, records)

    for record in records:
        write_location_info(settings, record)

    logger.info(
        "Wrote metadata for %d location(s) (%d sensor record(s)).",
        len(records),
        sum(len(r["sensors"]) for r in records),
    )
    return records
