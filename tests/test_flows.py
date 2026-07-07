"""Tests for the Prefect flows: ingest, clean, and the parent pipeline.

HTTP is mocked with respx; flows run against the session's prefect_test_harness.
"""

from __future__ import annotations

import json
import re
from unittest.mock import Mock, patch

import httpx
import pandas as pd
import pytest
import respx
import yaml

from aqmesh_pipeline.diagnostics import diagnostics_path
from aqmesh_pipeline.flows.clean import clean_data, clean_location_param
from aqmesh_pipeline.flows.ingest import ingest_raw
from aqmesh_pipeline.flows.metadata import sync_location_metadata
from aqmesh_pipeline.flows.pipeline import pipeline
from aqmesh_pipeline.models import Asset, Param
from aqmesh_pipeline.storage import (
    assets_path,
    clean_csv_path,
    clean_csvw_path,
    clean_metadata_path,
    load_assets,
    load_pointers,
    raw_param_dir,
    raw_store_descriptor_path,
    resampled_csv_path,
    save_assets,
)


def _allow_prefect():
    """Let the in-process ephemeral Prefect server's localhost traffic through respx."""
    respx.route(host="127.0.0.1").pass_through()
    respx.route(host="localhost").pass_through()


def _mock_api(base_url, assets_payload, gas_batch, particle_batch):
    """Register auth, assets, and per-location cursor routes (one batch then 204)."""
    _allow_prefect()
    respx.post(f"{base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for asset in assets_payload:
        loc = asset["location_number"]
        for param, batch in ((Param.GAS, gas_batch), (Param.PARTICLE, particle_batch)):
            url = f"{base_url}/LocationData/Next/{loc}/{int(param)}/01/1"
            respx.get(url).mock(side_effect=[httpx.Response(200, json=batch), httpx.Response(204)])


def _mock_metadata(base_url, assets_payload, sensor_detail_payload=None):
    """Register auth, assets, and sensor-detail routes for the metadata flow."""
    _allow_prefect()
    respx.post(f"{base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    respx.get(f"{base_url}/sensor/SensorDetail/0").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload or [])
    )


@respx.mock
def test_ingest_raw_writes_data_and_pointers(settings, assets_payload, gas_batch, particle_batch):
    _mock_api(settings.base_url, assets_payload, gas_batch, particle_batch)

    summary = ingest_raw(settings)

    assert summary["locations"] == 2
    # Raw files written for every location/param pair.
    assert list(raw_param_dir(settings, 510, Param.GAS).glob("*.json"))
    assert list(raw_param_dir(settings, 915, Param.PARTICLE).glob("*.json"))

    pointers = load_pointers(settings)
    assert pointers["510"]["gas"]["new_readings"] == len(gas_batch)
    assert pointers["510"]["gas"]["last_reading_number"] == 3256955

    # Asset snapshot persisted so the offline clean stage can read provenance.
    assert assets_path(settings).exists()
    snapshot = {a["location_number"] for a in json.loads(assets_path(settings).read_text())}
    assert snapshot == {510, 915}

    # Raw store descriptor written alongside the data volume.
    desc_path = raw_store_descriptor_path(settings)
    assert desc_path.exists()
    desc = yaml.safe_load(desc_path.read_text())
    assert desc["name"] == "aqmesh-raw"
    resources = {r["name"]: r for r in desc["resources"]}
    assert "raw-gas-510" in resources
    assert resources["raw-gas-510"]["last_reading_number"] == 3256955
    assert resources["raw-gas-510"]["location_name"] == "Sheffield City Centre"
    assert resources["raw-gas-510"]["status_this_run"] == "ok"
    assert resources["raw-gas-510"]["new_readings_this_run"] == len(gas_batch)


@respx.mock
def test_ingest_raw_continues_when_gas_fails(
    settings, assets_payload, particle_batch, gas_batch, monkeypatch
):
    """A persistent gas (Param=1) 500 must not abort the run; particle still flows (issue #9)."""
    # Skip the client's backoff sleeps so the exhausted-retry path is fast.
    monkeypatch.setattr("aqmesh_pipeline.client.time.sleep", lambda _seconds: None)
    _allow_prefect()
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for asset in assets_payload:
        loc = asset["location_number"]
        gas_url = f"{settings.base_url}/LocationData/Next/{loc}/{int(Param.GAS)}/01/1"
        particle_url = f"{settings.base_url}/LocationData/Next/{loc}/{int(Param.PARTICLE)}/01/1"
        respx.get(gas_url).mock(return_value=httpx.Response(500, text="upstream boom"))
        respx.get(particle_url).mock(
            side_effect=[httpx.Response(200, json=particle_batch), httpx.Response(204)]
        )

    summary = ingest_raw(settings)

    assert summary["locations"] == 2
    # Particle data flowed for every location despite gas failing.
    assert list(raw_param_dir(settings, 510, Param.PARTICLE).glob("*.json"))
    assert list(raw_param_dir(settings, 915, Param.PARTICLE).glob("*.json"))
    # Gas wrote nothing.
    assert not list(raw_param_dir(settings, 510, Param.GAS).glob("*.json"))

    pointers = load_pointers(settings)
    assert pointers["510"]["particle"]["new_readings"] == len(particle_batch)
    # Failed gas poll left no pointer rather than clobbering it.
    assert "gas" not in pointers["510"]

    gas_summaries = [s for s in summary["summaries"] if s["param"] == "gas"]
    assert gas_summaries and all(s["status"] == "failed" for s in gas_summaries)

    # The 500 response body is persisted for later debugging (issue #134).
    diag_path = diagnostics_path(settings)
    assert diag_path.exists()
    records = [json.loads(line) for line in diag_path.read_text().splitlines()]
    gas_errors = [r for r in records if r["stage"] == "ingest" and r["param"] == "gas"]
    assert gas_errors
    assert all(r["status_code"] == 500 for r in gas_errors)
    assert all(r["response_body"] == "upstream boom" for r in gas_errors)


@respx.mock
def test_ingest_raw_skips_404_locations(
    settings, assets_payload, gas_batch, particle_batch, monkeypatch
):
    """Locations returning HTTP 404 must be skipped with status 'not_found', not raise."""
    # assets_payload has locations 510 and 915; 915 returns 404 (not yet deployed).
    _allow_prefect()
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for param in (Param.GAS, Param.PARTICLE):
        respx.get(f"{settings.base_url}/LocationData/Next/510/{int(param)}/01/1").mock(
            side_effect=[
                httpx.Response(200, json=gas_batch if param == Param.GAS else particle_batch),
                httpx.Response(204),
            ]
        )
        respx.get(f"{settings.base_url}/LocationData/Next/915/{int(param)}/01/1").mock(
            return_value=httpx.Response(404, text="pod not deployed")
        )

    summary = ingest_raw(settings)

    ok = [s for s in summary["summaries"] if s["status"] == "ok"]
    not_found = [s for s in summary["summaries"] if s["status"] == "not_found"]
    assert all(s["location_number"] == 510 for s in ok)
    assert all(s["location_number"] == 915 for s in not_found)
    assert len(not_found) == 2  # gas + particle

    pointers = load_pointers(settings)
    # A 404 location advances no pointer, so it auto-recovers once the pod comes online.
    assert "915" not in pointers
    # The healthy location still recorded its progress.
    assert pointers["510"]["gas"]["new_readings"] == len(gas_batch)

    # The 404 response body is persisted for later debugging (issue #134).
    records = [json.loads(line) for line in diagnostics_path(settings).read_text().splitlines()]
    not_found_errors = [r for r in records if r["location_number"] == 915]
    assert len(not_found_errors) == 2  # gas + particle
    assert all(r["status_code"] == 404 for r in not_found_errors)
    assert all(r["response_body"] == "pod not deployed" for r in not_found_errors)


@respx.mock
def test_descriptor_marks_404_pod_offline(settings, assets_payload, gas_batch, particle_batch):
    """Previously-live pod that now 404s must appear in the descriptor with
    status_this_run='not_found', not silently retain a stale last_reading_number."""
    from aqmesh_pipeline.storage import save_pointers

    # Pre-seed pointers as if location 915 had prior successful readings.
    save_pointers(
        settings,
        {
            "915": {
                "gas": {
                    "last_reading_number": 99999,
                    "last_datestamp": "2025-01-01T00:00:00",
                    "new_readings": 10,
                },
                "particle": {
                    "last_reading_number": 99998,
                    "last_datestamp": "2025-01-01T00:00:00",
                    "new_readings": 8,
                },
            }
        },
    )
    _allow_prefect()
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for param in (Param.GAS, Param.PARTICLE):
        respx.get(f"{settings.base_url}/LocationData/Next/510/{int(param)}/01/1").mock(
            side_effect=[
                httpx.Response(200, json=gas_batch if param == Param.GAS else particle_batch),
                httpx.Response(204),
            ]
        )
        respx.get(f"{settings.base_url}/LocationData/Next/915/{int(param)}/01/1").mock(
            return_value=httpx.Response(404)
        )

    ingest_raw(settings)

    desc = yaml.safe_load(raw_store_descriptor_path(settings).read_text())
    resources = {r["name"]: r for r in desc["resources"]}

    # Offline pod must signal its status clearly.
    assert resources["raw-gas-915"]["status_this_run"] == "not_found"
    assert resources["raw-gas-915"]["new_readings_this_run"] == 0
    # Stale pointer is preserved (not advanced by the failed poll).
    assert resources["raw-gas-915"]["last_reading_number"] == 99999

    # Healthy pod still shows ok.
    assert resources["raw-gas-510"]["status_this_run"] == "ok"


@respx.mock
def test_descriptor_uses_fresh_assets_not_stale_snapshot(
    settings, assets_payload, gas_batch, particle_batch
):
    """Descriptor must reflect the freshly-fetched assets, not a stale disk snapshot."""
    # Seed stale assets.json with a wrong location name.
    stale = [dict(a, location_name="STALE NAME") for a in assets_payload]
    assets_path(settings).parent.mkdir(parents=True, exist_ok=True)
    assets_path(settings).write_text(json.dumps(stale))

    _mock_api(settings.base_url, assets_payload, gas_batch, particle_batch)
    ingest_raw(settings)

    desc = yaml.safe_load(raw_store_descriptor_path(settings).read_text())
    resources = {r["name"]: r for r in desc["resources"]}
    assert resources["raw-gas-510"]["location_name"] == "Sheffield City Centre"


@respx.mock
def test_ingest_raw_continues_when_descriptor_write_fails(
    settings, assets_payload, gas_batch, particle_batch, monkeypatch
):
    """A descriptor write failure must not prevent ingest from returning normally."""
    _mock_api(settings.base_url, assets_payload, gas_batch, particle_batch)
    monkeypatch.setattr(
        "aqmesh_pipeline.flows.ingest.write_raw_store_descriptor",
        Mock(side_effect=OSError("disk full")),
    )

    summary = ingest_raw(settings)

    # Raw data and pointers are still written.
    assert list(raw_param_dir(settings, 510, Param.GAS).glob("*.json"))
    pointers = load_pointers(settings)
    assert pointers["510"]["gas"]["new_readings"] == len(gas_batch)
    # Descriptor was not written, but the flow still returned successfully.
    assert not raw_store_descriptor_path(settings).exists()
    assert summary["locations"] == 2


@respx.mock
def test_clean_data_writes_one_csv_per_param(seed_raw):
    _allow_prefect()
    results = clean_data(seed_raw)

    written = [r for r in results if r["csv"]]
    assert len(written) == 2  # gas + particle for location 510
    assert clean_csv_path(seed_raw, 510, Param.GAS).exists()
    assert clean_csv_path(seed_raw, 510, Param.PARTICLE).exists()

    # Each CSV has a sibling metadata sidecar whose columns match the CSV header.
    for param in (Param.GAS, Param.PARTICLE):
        meta_path = clean_metadata_path(seed_raw, 510, param)
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        csv_cols = list(pd.read_csv(clean_csv_path(seed_raw, 510, param)).columns)
        assert set(meta["columns"]) == set(csv_cols)
        # Provenance flowed from the persisted asset snapshot.
        assert meta["provenance"]["location_name"] == "Sheffield City Centre"
        assert meta["provenance"]["latitude"] == 53.38
    # Gas units came from the raw <sp>_units field.
    gas_meta = json.loads(clean_metadata_path(seed_raw, 510, Param.GAS).read_text())
    assert gas_meta["columns"]["co"]["units"] == "ppb"

    # Each CSV has a sibling CSVW descriptor whose column order matches the CSV.
    for param in (Param.GAS, Param.PARTICLE):
        csvw_path = clean_csvw_path(seed_raw, 510, param)
        assert csvw_path.exists(), f"CSVW missing for {param.label}"
        doc = json.loads(csvw_path.read_text())
        assert "http://www.w3.org/ns/csvw" in doc["@context"]
        assert doc["url"] == clean_csv_path(seed_raw, 510, param).name
        csv_cols = list(pd.read_csv(clean_csv_path(seed_raw, 510, param)).columns)
        csvw_names = [c["name"] for c in doc["tableSchema"]["columns"]]
        assert csvw_names == csv_cols
    # Provenance with coordinates yields dcat:spatial.
    gas_doc = json.loads(clean_csvw_path(seed_raw, 510, Param.GAS).read_text())
    assert gas_doc["dcat:spatial"]["geo:lat"] == 53.38


@respx.mock
def test_clean_data_writes_resampled_csv_by_default(seed_raw):
    _allow_prefect()
    results = clean_data(seed_raw)

    # Both the per-reading and resampled CSVs are produced for each param.
    assert all(r["resampled_csv"] for r in results if r["csv"])
    assert clean_csv_path(seed_raw, 510, Param.GAS).exists()
    assert resampled_csv_path(seed_raw, 510, Param.GAS).exists()
    assert resampled_csv_path(seed_raw, 510, Param.PARTICLE).exists()


@respx.mock
def test_clean_data_no_resample_skips_resampled_csv(seed_raw):
    _allow_prefect()
    results = clean_data(seed_raw, resample=False)

    # Per-reading CSVs still written; resampled tree is not.
    assert all(r["resampled_csv"] is None for r in results)
    assert clean_csv_path(seed_raw, 510, Param.GAS).exists()
    assert not resampled_csv_path(seed_raw, 510, Param.GAS).exists()
    assert not seed_raw.resampled_dir.exists()


@respx.mock
def test_clean_location_param_resample_failure_leaves_no_partial_output(seed_raw):
    """If resample_daily raises, neither the clean CSV nor the metadata sidecar is written."""
    _allow_prefect()
    with (
        patch("aqmesh_pipeline.flows.clean.resample_daily", side_effect=ValueError("boom")),
        pytest.raises(ValueError),
    ):
        clean_location_param.fn(seed_raw, 510, Param.GAS, resample=True)

    assert not clean_csv_path(seed_raw, 510, Param.GAS).exists()
    assert not clean_metadata_path(seed_raw, 510, Param.GAS).exists()


def test_reading_datestamp_serialised_as_iso(seed_raw):
    _allow_prefect()
    clean_data(seed_raw)

    iso_ts = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    for csv_path in (
        clean_csv_path(seed_raw, 510, Param.GAS),
        resampled_csv_path(seed_raw, 510, Param.GAS),
    ):
        raw = pd.read_csv(csv_path, dtype=str)
        timestamps = raw["reading_datestamp"].dropna()
        assert len(timestamps) > 0, f"No timestamps in {csv_path.name}"
        bad = [v for v in timestamps if not iso_ts.match(v)]
        assert not bad, f"Unexpected format in {csv_path.name}: {bad}"


@respx.mock
def test_clean_data_no_raw_is_noop(settings):
    _allow_prefect()
    # raw_dir does not exist yet -> nothing to clean.
    results = clean_data(settings)
    assert results == []


@respx.mock
def test_clean_raises_when_asset_registry_is_empty(settings):
    _allow_prefect()
    # assets.json present but empty (e.g. API returned zero pods) -> fail fast.
    save_assets(settings, [])
    with pytest.raises(RuntimeError, match="Asset registry.*empty"):
        clean_data(settings)


@respx.mock
def test_clean_location_param_noop_when_empty(settings):
    _allow_prefect()
    # A location dir exists but holds no readings -> rows 0, no CSV written.
    raw_param_dir(settings, 510, Param.GAS).mkdir(parents=True)
    results = clean_data(settings)
    assert all(r["rows"] == 0 and r["csv"] is None for r in results)
    assert not clean_csv_path(settings, 510, Param.GAS).exists()


@respx.mock
def test_sync_location_metadata_writes_info_and_assets(
    settings, assets_payload, sensor_detail_payload
):
    """Metadata flow must write state/assets.json and info.json for every registered location."""
    _mock_metadata(settings.base_url, assets_payload, sensor_detail_payload)

    records = sync_location_metadata(settings)

    assert len(records) == 2
    assert {r["location_number"] for r in records} == {510, 915}

    saved = load_assets(settings)
    assert len(saved) == 2

    for loc in (510, 915):
        info_path = settings.clean_dir / f"location={loc}" / "info.json"
        assert info_path.exists(), f"info.json missing for location {loc}"
        data = json.loads(info_path.read_text())
        assert data["location_number"] == loc
        assert "sensors" in data


@respx.mock
def test_sync_location_metadata_joins_sensors_to_locations(
    settings, assets_payload, sensor_detail_payload
):
    """Sensor details must be joined to their pod's location by serial_number."""
    _mock_metadata(settings.base_url, assets_payload, sensor_detail_payload)

    records = sync_location_metadata(settings)

    # assets_payload has serial 2410103 for location 915; sensor_detail_payload also
    # references serial 2410103, so location 915's info.json should carry those sensors.
    loc_915 = next(r for r in records if r["location_number"] == 915)
    assert len(loc_915["sensors"]) == len(sensor_detail_payload)

    # location 510 (serial 2410149) has no matching sensors in the fixture.
    loc_510 = next(r for r in records if r["location_number"] == 510)
    assert loc_510["sensors"] == []


@respx.mock
def test_sync_location_metadata_continues_when_sensor_details_fail(settings, assets_payload):
    """A SensorDetail 404 (issue #116) must not block asset/location metadata from syncing."""
    _allow_prefect()
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    respx.get(f"{settings.base_url}/sensor/SensorDetail/0").mock(
        return_value=httpx.Response(404, text="sensor route not found")
    )

    records = sync_location_metadata(settings)

    assert len(records) == 2
    assert {r["location_number"] for r in records} == {510, 915}
    assert all(r["sensors"] == [] for r in records)

    saved = load_assets(settings)
    assert len(saved) == 2

    for loc in (510, 915):
        info_path = settings.clean_dir / f"location={loc}" / "info.json"
        assert info_path.exists(), f"info.json missing for location {loc}"

    # The SensorDetail failure body is persisted for later debugging (issue #134).
    diag_records = [
        json.loads(line) for line in diagnostics_path(settings).read_text().splitlines()
    ]
    metadata_errors = [r for r in diag_records if r["stage"] == "metadata"]
    assert len(metadata_errors) == 1
    assert metadata_errors[0]["call"] == "get_sensor_details"
    assert metadata_errors[0]["status_code"] == 404
    assert metadata_errors[0]["response_body"] == "sensor route not found"


@respx.mock
def test_clean_includes_404_location(settings, gas_batch, particle_batch):
    """A location in the asset registry with no raw data must appear in clean results."""
    _allow_prefect()
    # Seed state/assets.json with two locations: 510 (has raw data) and 4975 (does not).
    save_assets(
        settings,
        [
            Asset(location_number=510, serial_number=2410149),
            Asset(location_number=4975, serial_number=9999999),
        ],
    )
    # Seed raw data for location 510 only.
    from aqmesh_pipeline.storage import write_raw_batch

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(
        settings, 510, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )

    results = clean_data(settings)

    location_numbers = {r["location_number"] for r in results}
    assert 510 in location_numbers
    assert 4975 in location_numbers

    # 404 location: no CSV written, but it appears in the results.
    not_found = [r for r in results if r["location_number"] == 4975]
    assert all(r["rows"] == 0 and r["csv"] is None for r in not_found)

    # Healthy location: CSVs written.
    assert clean_csv_path(settings, 510, Param.GAS).exists()
    assert clean_csv_path(settings, 510, Param.PARTICLE).exists()


@respx.mock
def test_pipeline_end_to_end(monkeypatch, tmp_path, assets_payload, gas_batch, particle_batch):
    monkeypatch.setenv("AQMESH_USERNAME", "test-user")
    monkeypatch.setenv("AQMESH_PASSWORD", "test-pass")
    monkeypatch.setenv("AQMESH_ENVIRONMENT", "test")
    monkeypatch.setenv("AQMESH_DATA_ROOT", str(tmp_path))

    base_url = "https://apitest.aqmeshdata.net/api"
    _mock_api(base_url, assets_payload, gas_batch, particle_batch)
    respx.get(f"{base_url}/sensor/SensorDetail/0").mock(return_value=httpx.Response(200, json=[]))

    result = pipeline()

    assert result["ingest"]["locations"] == 2
    assert any(r["csv"] for r in result["clean"])
    assert result["validate"].keys() == {"checked", "valid", "invalid", "invalid_files"}
    # All registered locations should appear in the asset registry after the pipeline.
    from aqmesh_pipeline.config import Settings as S

    saved = load_assets(S(username="test-user", password="test-pass", data_root=tmp_path))
    assert set(saved.keys()) == {510, 915}
    # README.txt should be written to the data root on every pipeline run.
    readme = tmp_path / "README.txt"
    assert readme.exists()
    assert "raw/" in readme.read_text()


@respx.mock
def test_clean_data_csvw_no_spatial_when_no_coords(settings, gas_batch, particle_batch):
    """CSVW must not include dcat:spatial when the asset has no coordinates."""
    _allow_prefect()
    from aqmesh_pipeline.storage import write_raw_batch

    write_raw_batch(settings, 915, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(
        settings, 915, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )
    # Asset 915 has no latitude/longitude.
    save_assets(settings, [Asset(location_number=915, serial_number=2410103)])

    clean_data(settings)

    for param in (Param.GAS, Param.PARTICLE):
        csvw_path = clean_csvw_path(settings, 915, param)
        assert csvw_path.exists()
        doc = json.loads(csvw_path.read_text())
        assert "dcat:spatial" not in doc


@respx.mock
def test_clean_location_param_result_includes_csvw_key(seed_raw):
    """Every result dict from clean_data must carry a 'csvw' key."""
    _allow_prefect()
    results = clean_data(seed_raw)

    for r in results:
        assert "csvw" in r, f"'csvw' key missing from result: {r}"
    # Locations with data have a non-None csvw path alongside their csv.
    written = [r for r in results if r["csv"]]
    assert all(r["csvw"] is not None for r in written)


@respx.mock
def test_pipeline_continues_when_metadata_sync_fails(
    monkeypatch, tmp_path, assets_payload, gas_batch, particle_batch
):
    """ingest_raw() must run even when sync_location_metadata() raises."""
    monkeypatch.setenv("AQMESH_USERNAME", "test-user")
    monkeypatch.setenv("AQMESH_PASSWORD", "test-pass")
    monkeypatch.setenv("AQMESH_ENVIRONMENT", "test")
    monkeypatch.setenv("AQMESH_DATA_ROOT", str(tmp_path))

    monkeypatch.setattr(
        "aqmesh_pipeline.flows.pipeline.sync_location_metadata",
        Mock(side_effect=RuntimeError("sensor-detail 500")),
    )

    base_url = "https://apitest.aqmeshdata.net/api"
    _mock_api(base_url, assets_payload, gas_batch, particle_batch)

    result = pipeline()

    assert result["ingest"]["locations"] > 0


@respx.mock
def test_pipeline_continues_when_validation_fails(
    monkeypatch, tmp_path, assets_payload, gas_batch, particle_batch
):
    """clean_data() must still run, and result['validate'] must be None, when validation raises."""
    monkeypatch.setenv("AQMESH_USERNAME", "test-user")
    monkeypatch.setenv("AQMESH_PASSWORD", "test-pass")
    monkeypatch.setenv("AQMESH_ENVIRONMENT", "test")
    monkeypatch.setenv("AQMESH_DATA_ROOT", str(tmp_path))

    monkeypatch.setattr(
        "aqmesh_pipeline.flows.pipeline.validate_raw_store",
        Mock(side_effect=RuntimeError("validation blew up")),
    )

    base_url = "https://apitest.aqmeshdata.net/api"
    _mock_api(base_url, assets_payload, gas_batch, particle_batch)
    respx.get(f"{base_url}/sensor/SensorDetail/0").mock(return_value=httpx.Response(200, json=[]))

    result = pipeline()

    assert result["validate"] is None
    assert any(r["csv"] for r in result["clean"])
