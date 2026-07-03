"""Tests for raw JSON batch validation (validate.py and flows/validate.py)."""

from __future__ import annotations

import json

from aqmesh_pipeline.models import Param
from aqmesh_pipeline.storage import write_raw_batch
from aqmesh_pipeline.validate import load_schema, validate_raw_file

# ---------------------------------------------------------------------------
# load_schema
# ---------------------------------------------------------------------------


def test_load_schema_gas():
    schema = load_schema(Param.GAS)
    assert schema["title"] == "AQMesh raw gas reading"
    assert "gas_reading_number" in schema["required"]


def test_load_schema_particle():
    schema = load_schema(Param.PARTICLE)
    assert schema["title"] == "AQMesh raw particle reading"
    assert "particle_reading_number" in schema["required"]


# ---------------------------------------------------------------------------
# validate_raw_file
# ---------------------------------------------------------------------------


def test_validate_raw_file_valid(tmp_path, gas_batch):
    schema = load_schema(Param.GAS)
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(gas_batch), encoding="utf-8")
    assert validate_raw_file(f, schema) == []


def test_validate_raw_file_missing_required_field(tmp_path, gas_batch):
    schema = load_schema(Param.GAS)
    bad = [{k: v for k, v in r.items() if k != "gas_reading_number"} for r in gas_batch]
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    errors = validate_raw_file(f, schema)
    assert len(errors) == len(bad)
    assert all("gas_reading_number" in e["message"] for e in errors)


def test_validate_raw_file_empty_array(tmp_path):
    schema = load_schema(Param.GAS)
    f = tmp_path / "batch.json"
    f.write_text("[]", encoding="utf-8")
    assert validate_raw_file(f, schema) == []


def test_validate_raw_file_null_json(tmp_path):
    schema = load_schema(Param.GAS)
    f = tmp_path / "batch.json"
    f.write_text("null", encoding="utf-8")
    errors = validate_raw_file(f, schema)
    assert errors == [
        {"record_index": -1, "message": "Expected JSON array, got NoneType", "path": []}
    ]


def test_validate_raw_file_object_not_array(tmp_path):
    schema = load_schema(Param.GAS)
    f = tmp_path / "batch.json"
    f.write_text("{}", encoding="utf-8")
    errors = validate_raw_file(f, schema)
    assert errors == [{"record_index": -1, "message": "Expected JSON array, got dict", "path": []}]


def test_validate_raw_file_particle_valid(tmp_path, particle_batch):
    schema = load_schema(Param.PARTICLE)
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(particle_batch), encoding="utf-8")
    assert validate_raw_file(f, schema) == []


def test_validate_raw_file_error_includes_record_index(tmp_path, gas_batch):
    schema = load_schema(Param.GAS)
    bad = [gas_batch[0], {k: v for k, v in gas_batch[1].items() if k != "gas_reading_number"}]
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    errors = validate_raw_file(f, schema)
    assert len(errors) == 1
    assert errors[0]["record_index"] == 1


# ---------------------------------------------------------------------------
# validate_raw_store flow
# ---------------------------------------------------------------------------


def test_validate_raw_store_valid(settings, gas_batch, particle_batch):
    from aqmesh_pipeline.flows.validate import validate_raw_store

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(
        settings, 510, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )
    report = validate_raw_store(settings)
    assert report["invalid"] == 0
    assert report["checked"] == 2


def test_validate_raw_store_detects_invalid(settings, gas_batch):
    from aqmesh_pipeline.flows.validate import validate_raw_store
    from aqmesh_pipeline.storage import raw_param_dir

    # Write a batch with missing required field
    bad = [{k: v for k, v in r.items() if k != "gas_reading_number"} for r in gas_batch]
    param_dir = raw_param_dir(settings, 510, Param.GAS)
    param_dir.mkdir(parents=True, exist_ok=True)
    (param_dir / "20260101T000000Z_0.json").write_text(json.dumps(bad), encoding="utf-8")

    report = validate_raw_store(settings)
    assert report["invalid"] == 1
    assert report["errors"][0]["location"] == 510


def test_validate_raw_store_skips_zero_new_readings(settings, gas_batch):
    from aqmesh_pipeline.flows.validate import validate_raw_store

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    summaries = [{"location_number": 510, "param": "gas", "new_readings": 0, "status": "ok"}]
    report = validate_raw_store(settings, summaries=summaries)
    assert report["checked"] == 0


def test_validate_raw_store_skips_failed_status(settings, gas_batch):
    from aqmesh_pipeline.flows.validate import validate_raw_store

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    summaries = [{"location_number": 510, "param": "gas", "new_readings": 5, "status": "failed"}]
    report = validate_raw_store(settings, summaries=summaries)
    assert report["checked"] == 0


def test_validate_raw_store_with_summaries_only_checks_new(settings, gas_batch, particle_batch):
    from aqmesh_pipeline.flows.validate import validate_raw_store

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(
        settings, 510, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )
    # Only gas had new readings
    summaries = [
        {"location_number": 510, "param": "gas", "new_readings": 2, "status": "ok"},
        {"location_number": 510, "param": "particle", "new_readings": 0, "status": "ok"},
    ]
    report = validate_raw_store(settings, summaries=summaries)
    assert report["checked"] == 1
    assert report["invalid"] == 0


def test_validate_raw_store_no_files(settings):
    from aqmesh_pipeline.flows.validate import validate_raw_store

    report = validate_raw_store(settings)
    assert report == {"checked": 0, "valid": 0, "invalid": 0, "errors": []}
