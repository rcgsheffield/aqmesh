"""Tests for the clean-CSV metadata sidecar builder (issue #58)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from aqmesh_pipeline.metadata import (
    READING_STATUS_LEGEND,
    build_metadata,
    extract_species_units,
)
from aqmesh_pipeline.models import Asset, Param
from aqmesh_pipeline.transform import clean_readings

_GENERATED_AT = datetime(2026, 6, 19, 9, 30, tzinfo=UTC)


def test_extract_species_units_reads_units_field():
    raw = pd.DataFrame([{"co_units": "ppb", "no2_units": "ppb"}, {"co_units": "ppb"}])
    units = extract_species_units(raw, ("co", "no2", "o3"))
    assert units == {"co": "ppb", "no2": "ppb"}  # o3 absent -> omitted


def test_build_metadata_gas_units_from_raw_and_calibrated_flags(settings, gas_batch):
    raw = pd.DataFrame(gas_batch)
    cleaned = clean_readings(raw, Param.GAS)
    asset = Asset(location_number=510, location_name="Site A", serial_number=2410149)

    meta = build_metadata(cleaned, raw, Param.GAS, asset, settings, _GENERATED_AT)

    # columns block exactly matches what was written to the CSV.
    assert set(meta["columns"]) == set(cleaned.columns)
    # gas units come from the raw <sp>_units field.
    assert meta["columns"]["co"]["units"] == "ppb"
    assert meta["columns"]["co"]["calibrated"] is True
    # passthrough/static columns are not calibrated and use the static units table.
    assert meta["columns"]["temperature_f"]["calibrated"] is False
    assert meta["columns"]["temperature_f"]["units"] == "degF"
    # identity columns carry no units.
    assert meta["columns"]["reading_datestamp"]["units"] is None


def test_build_metadata_provenance_from_asset(settings, gas_batch):
    raw = pd.DataFrame(gas_batch)
    cleaned = clean_readings(raw, Param.GAS)
    asset = Asset(
        location_number=510,
        location_name="Sheffield City Centre",
        serial_number=2410149,
        firmware_version="v3.22",
        location_latitude=53.38,
        location_longitude=-1.48,
    )

    meta = build_metadata(cleaned, raw, Param.GAS, asset, settings, _GENERATED_AT)

    prov = meta["provenance"]
    assert prov["location_name"] == "Sheffield City Centre"
    assert prov["latitude"] == 53.38
    assert prov["longitude"] == -1.48
    assert prov["firmware_version"] == "v3.22"
    assert prov["environment"] == "test"
    assert prov["generated_at"] == "2026-06-19T09:30:00+00:00"
    assert meta["location_number"] == 510
    assert meta["row_count"] == len(cleaned)
    assert meta["reading_status_legend"] == READING_STATUS_LEGEND


def test_build_metadata_without_asset_degrades_gracefully(settings, gas_batch):
    raw = pd.DataFrame(gas_batch)
    cleaned = clean_readings(raw, Param.GAS)

    meta = build_metadata(cleaned, raw, Param.GAS, None, settings, _GENERATED_AT)

    assert meta["provenance"]["location_name"] is None
    # location_number still recovered from the cleaned frame.
    assert meta["location_number"] == 510


def test_build_metadata_particle_static_units(settings, particle_batch):
    raw = pd.DataFrame(particle_batch)
    cleaned = clean_readings(raw, Param.PARTICLE)

    meta = build_metadata(cleaned, raw, Param.PARTICLE, None, settings, _GENERATED_AT)

    assert meta["param"] == "particle"
    assert meta["columns"]["pm2_5"]["units"] == "ug/m3"
    assert meta["columns"]["pm2_5"]["calibrated"] is True
    assert meta["columns"]["reading_status"]["calibrated"] is False
