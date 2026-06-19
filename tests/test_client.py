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
    url = f"{settings.base_url}/LocationData/Next/510/1/01/1"
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
    url = f"{settings.base_url}/LocationData/Next/510/1/01/1"
    respx.get(url).mock(
        side_effect=[httpx.Response(200, json=gas_batch), httpx.Response(200, json=[])]
    )
    with AQMeshClient(settings) as client:
        batches = list(client.iter_location_data(510, Param.GAS))
    assert len(batches) == 1


@respx.mock
def test_iter_location_data_path_has_four_segments_after_next(settings):
    """Regression for #8: the route 404s on a trailing /{version}, so the default
    (version=0) path must have exactly 4 segments after ``Next``."""
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx.get(url__regex=rf"{settings.base_url}/LocationData/Next/.*").mock(
        return_value=httpx.Response(204)
    )
    with AQMeshClient(settings) as client:
        list(client.iter_location_data(510, Param.GAS))

    requested = route.calls.last.request.url.path
    segments = requested.split("/LocationData/Next/")[1].split("/")
    assert segments == ["510", "1", "01", "1"]


@respx.mock
def test_iter_location_data_appends_non_default_version(settings):
    """A non-zero version is appended as the 5th segment (documented but rarely used)."""
    settings = settings.model_copy(update={"version": 3})
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx.get(url__regex=rf"{settings.base_url}/LocationData/Next/.*").mock(
        return_value=httpx.Response(204)
    )
    with AQMeshClient(settings) as client:
        list(client.iter_location_data(510, Param.GAS))

    requested = route.calls.last.request.url.path
    segments = requested.split("/LocationData/Next/")[1].split("/")
    assert segments == ["510", "1", "01", "1", "3"]


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


# -- repeat_last -------------------------------------------------------------


@respx.mock
def test_repeat_last_gas_calls_correct_path(settings, gas_batch):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx.get(url__regex=rf"{settings.base_url}/LocationData/Repeat/.*").mock(
        return_value=httpx.Response(200, json=gas_batch)
    )
    with AQMeshClient(settings) as client:
        result = client.repeat_last(510, Param.GAS)

    assert result == gas_batch
    path = route.calls.last.request.url.path
    segments = path.split("/LocationData/Repeat/")[1].split("/")
    # location / param / units  (no TPC, no version when version=0)
    assert segments == ["510", "1", "01"]


@respx.mock
def test_repeat_last_particle_uses_int_2(settings, particle_batch):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx.get(url__regex=rf"{settings.base_url}/LocationData/Repeat/.*").mock(
        return_value=httpx.Response(200, json=particle_batch)
    )
    with AQMeshClient(settings) as client:
        client.repeat_last(510, Param.PARTICLE)

    path = route.calls.last.request.url.path
    segments = path.split("/LocationData/Repeat/")[1].split("/")
    assert segments[1] == "2"


@respx.mock
def test_repeat_last_returns_empty_on_204(settings):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(url__regex=rf"{settings.base_url}/LocationData/Repeat/.*").mock(
        return_value=httpx.Response(204)
    )
    with AQMeshClient(settings) as client:
        result = client.repeat_last(510, Param.GAS)
    assert result == []


@respx.mock
def test_repeat_last_appends_non_default_version(settings, gas_batch):
    settings = settings.model_copy(update={"version": 2})
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx.get(url__regex=rf"{settings.base_url}/LocationData/Repeat/.*").mock(
        return_value=httpx.Response(200, json=gas_batch)
    )
    with AQMeshClient(settings) as client:
        client.repeat_last(510, Param.GAS)

    path = route.calls.last.request.url.path
    segments = path.split("/LocationData/Repeat/")[1].split("/")
    assert segments == ["510", "1", "01", "2"]
