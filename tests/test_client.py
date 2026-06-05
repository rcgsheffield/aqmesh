"""Tests for AQMeshClient: auth, the cursor loop, and 401 re-auth — all mocked."""

from __future__ import annotations

import httpx
import pytest
import respx

from aqmesh_pipeline.client import AQMeshAuthError, AQMeshClient
from aqmesh_pipeline.models import Param


@respx.mock
def test_get_assets(settings, assets_payload):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    with AQMeshClient(settings) as client:
        assets = client.get_assets()
    assert [a.location_number for a in assets] == [510, 915]


@respx.mock
def test_iter_location_data_stops_on_empty(settings, gas_batch):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    url = f"{settings.base_url}/LocationData/Next/510/1/01/1/0"
    respx.get(url).mock(
        side_effect=[
            httpx.Response(200, json=gas_batch),
            httpx.Response(200, json=gas_batch),
            httpx.Response(204),
        ]
    )
    with AQMeshClient(settings) as client:
        batches = list(client.iter_location_data(510, Param.GAS))
    assert len(batches) == 2
    assert all(len(b) == 2 for b in batches)


@respx.mock
def test_iter_location_data_stops_on_empty_array(settings, gas_batch):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    url = f"{settings.base_url}/LocationData/Next/510/1/01/1/0"
    respx.get(url).mock(
        side_effect=[httpx.Response(200, json=gas_batch), httpx.Response(200, json=[])]
    )
    with AQMeshClient(settings) as client:
        batches = list(client.iter_location_data(510, Param.GAS))
    assert len(batches) == 1


@respx.mock
def test_reauth_on_401(settings, assets_payload):
    auth = respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json=assets_payload),
        ]
    )
    with AQMeshClient(settings) as client:
        assets = client.get_assets()
    assert len(assets) == 2
    assert auth.call_count == 2  # re-authenticated after the 401


@respx.mock
def test_authenticate_failure_raises(settings):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with AQMeshClient(settings) as client, pytest.raises(AQMeshAuthError):
        client.authenticate()


@respx.mock
def test_authenticate_without_token_raises(settings):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"not_a_token": True})
    )
    with AQMeshClient(settings) as client, pytest.raises(AQMeshAuthError):
        client.authenticate()


@pytest.fixture
def _no_backoff_sleep(monkeypatch):
    """Skip the real backoff sleeps so retry tests stay fast."""
    monkeypatch.setattr("aqmesh_pipeline.client.time.sleep", lambda _seconds: None)


@respx.mock
def test_get_retries_on_server_error_then_succeeds(settings, assets_payload, _no_backoff_sleep):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=assets_payload)]
    )
    with AQMeshClient(settings) as client:
        assets = client.get_assets()
    assert len(assets) == 2


@respx.mock
def test_get_retries_on_transport_error_then_succeeds(settings, assets_payload, _no_backoff_sleep):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=assets_payload)]
    )
    with AQMeshClient(settings) as client:
        assets = client.get_assets()
    assert len(assets) == 2


@respx.mock
def test_get_raises_after_exhausting_retries(settings, _no_backoff_sleep):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(return_value=httpx.Response(500))
    # settings.max_retries == 2 -> 3 attempts, all 500, then the last error is raised.
    with AQMeshClient(settings) as client, pytest.raises(httpx.HTTPStatusError):
        client.get_assets()
