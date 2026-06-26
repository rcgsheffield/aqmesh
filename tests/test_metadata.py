"""Tests for the clean-CSV metadata sidecar builder (issue #58) and raw store descriptor (#69)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from aqmesh_pipeline.metadata import (
    READING_STATUS_LEGEND,
    build_metadata,
    build_raw_store_descriptor,
    extract_species_units,
)
from aqmesh_pipeline.models import Asset, Param
from aqmesh_pipeline.storage import write_raw_batch
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


# ---------------------------------------------------------------------------
# build_raw_store_descriptor (issue #69)
# ---------------------------------------------------------------------------

_ASSETS = {
    510: Asset(
        location_number=510,
        location_name="Sheffield City Centre",
        serial_number=2410149,
        firmware_version="v3.22",
        location_latitude=53.38,
        location_longitude=-1.48,
    ),
    915: Asset(location_number=915, serial_number=2410103),
}


def _ptr(last_rn, last_ds, new):
    return {"last_reading_number": last_rn, "last_datestamp": last_ds, "new_readings": new}


_POINTERS = {
    "510": {
        "gas": _ptr(3256955, "2019-04-19T09:30:00", 2),
        "particle": _ptr(15622255, "2019-03-09T16:11:00", 1),
    },
    "915": {
        "gas": _ptr(100, "2019-04-01T00:00:00", 1),
        "particle": _ptr(200, "2019-04-01T00:00:00", 1),
    },
}


def _summary(loc, param, new, last_rn, last_ds, status="ok"):
    return {
        "location_number": loc,
        "param": param,
        "new_readings": new,
        "last_reading_number": last_rn,
        "last_datestamp": last_ds,
        "status": status,
    }


_SUMMARIES = [
    _summary(510, "gas", 2, 3256955, "2019-04-19T09:30:00"),
    _summary(510, "particle", 1, 15622255, "2019-03-09T16:11:00"),
    _summary(915, "gas", 1, 100, "2019-04-01T00:00:00"),
    _summary(915, "particle", 1, 200, "2019-04-01T00:00:00"),
]


def test_build_raw_store_descriptor_structure(settings):
    desc = build_raw_store_descriptor(_ASSETS, _POINTERS, _SUMMARIES, settings, _GENERATED_AT)

    assert desc["name"] == "aqmesh-raw"
    assert "title" in desc
    assert "licenses" in desc
    assert desc["generated_at"] == _GENERATED_AT.isoformat()
    assert desc["environment"] == "test"

    resources = {r["name"]: r for r in desc["resources"]}
    assert len(resources) == 4
    r = resources["raw-gas-510"]
    assert r["location_name"] == "Sheffield City Centre"
    assert r["last_reading_number"] == 3256955
    assert r["new_readings_this_run"] == 2
    assert "Sheffield City Centre" in r["title"]
    assert "gas" in r["schema"]["$ref"]


def test_build_raw_store_descriptor_missing_asset(settings):
    desc = build_raw_store_descriptor({}, _POINTERS, _SUMMARIES, settings, _GENERATED_AT)

    resources = {r["name"]: r for r in desc["resources"]}
    assert len(resources) == 4
    r = resources["raw-gas-510"]
    assert r["location_name"] is None
    assert r["latitude"] is None
    assert r["last_reading_number"] == 3256955


def test_build_raw_store_descriptor_failed_param(settings):
    summaries = [
        _summary(510, "gas", 0, None, None, status="failed"),
        _summary(510, "particle", 1, 15622255, "2019-03-09T16:11:00"),
    ]
    pointers = {
        "510": {
            "gas": _ptr(3256955, "2019-04-19T09:30:00", 0),
            "particle": _ptr(15622255, "2019-03-09T16:11:00", 1),
        }
    }
    desc = build_raw_store_descriptor(_ASSETS, pointers, summaries, settings, _GENERATED_AT)

    resources = {r["name"]: r for r in desc["resources"]}
    assert "new_readings_this_run" not in resources["raw-gas-510"]
    assert resources["raw-particle-510"]["new_readings_this_run"] == 1


def test_build_raw_store_descriptor_file_count(settings, gas_batch, particle_batch):
    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T010000Z", seq=0)
    write_raw_batch(
        settings, 510, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )
    pointers = {
        "510": {
            "gas": _ptr(3256955, "2019-04-19T09:30:00", 2),
            "particle": _ptr(15622255, "2019-03-09T16:11:00", 1),
        }
    }
    desc = build_raw_store_descriptor(_ASSETS, pointers, _SUMMARIES[:2], settings, _GENERATED_AT)

    resources = {r["name"]: r for r in desc["resources"]}
    assert resources["raw-gas-510"]["file_count"] == 2
    assert resources["raw-particle-510"]["file_count"] == 1
