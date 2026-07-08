"""Tests for the raw store, dedup-on-rebase, and pointer state round-trip."""

from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from aqmesh_client.models import Param
from aqmesh_pipeline.storage import (
    CorruptRawFileError,
    load_pointers,
    raw_param_dir,
    raw_store_descriptor_path,
    read_raw_readings,
    save_pointers,
    update_pointer,
    write_location_info,
    write_raw_batch,
    write_raw_store_descriptor,
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


def test_raw_store_descriptor_path(settings):
    assert raw_store_descriptor_path(settings) == settings.raw_dir / "datapackage.yaml"


def test_write_raw_store_descriptor_atomic(settings):
    path = raw_store_descriptor_path(settings)
    payload = {"name": "aqmesh-raw", "resources": []}
    write_raw_store_descriptor(payload, path)

    assert path.exists()
    assert not path.with_suffix(".yaml.tmp").exists()
    loaded = yaml.safe_load(path.read_text())
    assert loaded["name"] == "aqmesh-raw"
    assert loaded["resources"] == []


def test_interrupted_write_leaves_no_corrupt_file(settings, gas_batch):
    """A stale .tmp file (simulating a killed-mid-write process) must not
    be visible to the reader as a corrupt JSON file."""
    out_dir = raw_param_dir(settings, 510, Param.GAS)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    # Simulate crash after tmp write but before rename (seq=1).
    stale_tmp = out_dir / "20260101T010000Z_0001.json.tmp"
    stale_tmp.write_text(json.dumps(gas_batch), encoding="utf-8")

    # Reader's *.json glob must not match the .tmp file.
    df = read_raw_readings(settings, 510, Param.GAS)
    assert len(df) == 2  # only the first batch


def test_corrupt_raw_file_raises_clearly(settings):
    """A pre-existing corrupt raw file must raise CorruptRawFileError, not
    silently return an empty DataFrame."""
    out_dir = raw_param_dir(settings, 510, Param.GAS)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "20260101T000000Z_0000.json").write_text("{truncated", encoding="utf-8")

    with pytest.raises(CorruptRawFileError):
        read_raw_readings(settings, 510, Param.GAS)


def test_sha256_sidecar_written_with_batch(settings, gas_batch):
    """write_raw_batch must write a .sha256 sidecar alongside the JSON."""
    path = write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    sha_path = path.with_name(path.name + ".sha256")
    assert sha_path.exists()
    expected = hashlib.sha256(json.dumps(gas_batch).encode()).hexdigest()
    assert sha_path.read_text().strip() == expected


def test_checksum_mismatch_raises(settings, gas_batch):
    """A tampered raw file (checksum mismatch) must raise CorruptRawFileError."""
    path = write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    path.with_name(path.name + ".sha256").write_text("deadbeef" * 8, encoding="utf-8")

    with pytest.raises(CorruptRawFileError):
        read_raw_readings(settings, 510, Param.GAS)
