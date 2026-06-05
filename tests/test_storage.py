"""Tests for the raw store, dedup-on-rebase, and pointer state round-trip."""

from __future__ import annotations

from aqmesh_pipeline.models import Param
from aqmesh_pipeline.storage import (
    load_pointers,
    read_raw_readings,
    save_pointers,
    update_pointer,
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
