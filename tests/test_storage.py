"""Tests for the raw store, dedup-on-rebase, and pointer state round-trip."""

from __future__ import annotations

import json

from aqmesh_pipeline.models import Param
from aqmesh_pipeline.storage import (
    load_pointers,
    read_raw_readings,
    save_pointers,
    update_pointer,
    write_location_info,
    write_raw_batch,
)


def test_write_then_read_raw(settings, gas_batch):
    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    df = read_raw_readings(settings, 510, Param.GAS)
    assert len(df) == 2
    assert set(df["gas_reading_number"]) == {3256954, 3256955}


def test_rebased_value_overwrites_earlier(settings, gas_batch):
    # First pull.
    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    # Later pull re-sends reading 3256954 with a corrected (rebased) value.
    corrected = [{**gas_batch[0], "co_prescaled": 999.0}]
    write_raw_batch(settings, 510, Param.GAS, corrected, pulled_at="20260101T010000Z", seq=0)

    df = read_raw_readings(settings, 510, Param.GAS)
    assert len(df) == 2  # deduped, not duplicated
    row = df.loc[df["gas_reading_number"] == 3256954].iloc[0]
    assert row["co_prescaled"] == 999.0  # the later value wins


def test_read_missing_location_is_empty(settings):
    assert read_raw_readings(settings, 999, Param.GAS).empty


def test_read_empty_batches_is_empty(settings):
    # Files exist but contain no readings -> empty frame, not an error.
    write_raw_batch(settings, 510, Param.GAS, [], pulled_at="20260101T000000Z", seq=0)
    assert read_raw_readings(settings, 510, Param.GAS).empty


def test_read_without_reading_number_skips_dedup(settings):
    # Records lacking the reading-number field are returned as-is (no dedup key).
    records = [{"co_prescaled": 1.0}, {"co_prescaled": 2.0}]
    write_raw_batch(settings, 510, Param.GAS, records, pulled_at="20260101T000000Z", seq=0)
    df = read_raw_readings(settings, 510, Param.GAS)
    assert len(df) == 2
    assert "gas_reading_number" not in df.columns


def test_write_location_info_round_trip(settings):
    asset_data = {"location_number": 510, "name": "Test Pod"}
    path = write_location_info(settings, asset_data)
    assert path.exists()
    assert json.loads(path.read_text()) == asset_data


def test_pointers_round_trip(settings):
    pointers: dict = {}
    update_pointer(
        pointers,
        510,
        Param.GAS,
        last_reading_number=3256955,
        last_datestamp="2019-04-19T09:30:00",
        new_readings=2,
    )
    save_pointers(settings, pointers)

    loaded = load_pointers(settings)
    assert loaded["510"]["gas"]["last_reading_number"] == 3256955
    assert loaded["510"]["gas"]["new_readings"] == 2
