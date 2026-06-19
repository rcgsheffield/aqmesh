"""Tests for the Prefect flows: ingest, clean, and the parent pipeline.

HTTP is mocked with respx; flows run against the session's prefect_test_harness.
"""

from __future__ import annotations

import httpx
import respx

from aqmesh_pipeline.flows.clean import clean_data
from aqmesh_pipeline.flows.ingest import ingest_raw
from aqmesh_pipeline.flows.pipeline import pipeline
from aqmesh_pipeline.models import Param
from aqmesh_pipeline.storage import clean_csv_path, load_pointers, raw_param_dir


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
        respx.get(gas_url).mock(return_value=httpx.Response(500))
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
            return_value=httpx.Response(404)
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


@respx.mock
def test_clean_data_writes_one_csv_per_param(seed_raw):
    _allow_prefect()
    results = clean_data(seed_raw)

    written = [r for r in results if r["csv"]]
    assert len(written) == 2  # gas + particle for location 510
    assert clean_csv_path(seed_raw, 510, Param.GAS).exists()
    assert clean_csv_path(seed_raw, 510, Param.PARTICLE).exists()


@respx.mock
def test_clean_data_no_raw_is_noop(settings):
    _allow_prefect()
    # raw_dir does not exist yet -> nothing to clean.
    results = clean_data(settings)
    assert results == []


@respx.mock
def test_clean_location_param_noop_when_empty(settings):
    _allow_prefect()
    # A location dir exists but holds no readings -> rows 0, no CSV written.
    raw_param_dir(settings, 510, Param.GAS).mkdir(parents=True)
    results = clean_data(settings)
    assert all(r["rows"] == 0 and r["csv"] is None for r in results)
    assert not clean_csv_path(settings, 510, Param.GAS).exists()


@respx.mock
def test_pipeline_end_to_end(monkeypatch, tmp_path, assets_payload, gas_batch, particle_batch):
    monkeypatch.setenv("AQMESH_USERNAME", "test-user")
    monkeypatch.setenv("AQMESH_PASSWORD", "test-pass")
    monkeypatch.setenv("AQMESH_ENVIRONMENT", "test")
    monkeypatch.setenv("AQMESH_DATA_ROOT", str(tmp_path))

    base_url = "https://apitest.aqmeshdata.net/api"
    _mock_api(base_url, assets_payload, gas_batch, particle_batch)

    result = pipeline()

    assert result["ingest"]["locations"] == 2
    assert any(r["csv"] for r in result["clean"])
