"""Tests for the standalone `aqmesh_client.cli` module (issue #136)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from aqmesh_client import cli
from aqmesh_client.cli import assets, fetch, notifications, ping, repeat, sensors


def _mock_auth(base_url: str) -> None:
    respx.post(f"{base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )


# -- ping ---------------------------------------------------------------------


@respx.mock
def test_ping_success(settings, serverping_payload, capsys):
    respx.get(f"{settings.base_url}/serverping").mock(
        return_value=httpx.Response(200, json=serverping_payload)
    )
    ping([], settings)
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == "Vn 0.9"
    assert out["most_recent_reading"] == "2026-06-19T08:57:00"


@respx.mock
def test_ping_unreachable_exits_nonzero(settings, capsys):
    respx.get(f"{settings.base_url}/serverping").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        ping([], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


@respx.mock
def test_ping_works_without_credentials(monkeypatch, tmp_path, serverping_payload, capsys):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.delenv("AQMESH_ENVIRONMENT", raising=False)
    monkeypatch.chdir(tmp_path)
    base = "https://apitest.aqmeshdata.net/api"
    respx.get(f"{base}/serverping").mock(return_value=httpx.Response(200, json=serverping_payload))
    ping([])
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == "Vn 0.9"


@respx.mock
def test_ping_pretty_indented(settings, serverping_payload, capsys):
    respx.get(f"{settings.base_url}/serverping").mock(
        return_value=httpx.Response(200, json=serverping_payload)
    )
    ping(["--pretty"], settings)
    assert "\n  " in capsys.readouterr().out


# -- assets ---------------------------------------------------------------------


@respx.mock
def test_assets_success(settings, assets_payload, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    assets([], settings)
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2
    assert out[0]["location_number"] == 510


@respx.mock
def test_assets_empty_not_an_error(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(return_value=httpx.Response(200, json=[]))
    assets([], settings)
    assert json.loads(capsys.readouterr().out) == []


@respx.mock
def test_assets_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        assets([], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().err


@respx.mock
def test_assets_network_failure_exits_nonzero(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        assets([], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


def test_assets_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        assets([])
    assert exc_info.value.code == 1


# -- sensors ---------------------------------------------------------------------


@respx.mock
def test_sensors_success(settings, sensor_detail_payload, failed_sensor_payload, capsys):
    _mock_auth(settings.base_url)
    respx.get(url__regex=rf"{settings.base_url}/sensor/SensorDetail.*").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload)
    )
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    sensors([], settings)
    out = json.loads(capsys.readouterr().out)
    assert len(out["sensors"]) == 2
    assert len(out["failed_sensors"]) == 1


@respx.mock
def test_sensors_active_flag(settings, sensor_detail_payload, failed_sensor_payload):
    _mock_auth(settings.base_url)
    route = respx.get(url__regex=rf"{settings.base_url}/sensor/SensorDetail.*").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload)
    )
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    sensors(["--active"], settings)
    assert route.calls.last.request.url.path.endswith("/sensor/SensorDetail/1")


@respx.mock
def test_sensors_failed_only_omits_sensors_key(settings, failed_sensor_payload, capsys):
    _mock_auth(settings.base_url)
    # No SensorDetail route registered: --failed-only must not call it.
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    sensors(["--failed-only"], settings)
    out = json.loads(capsys.readouterr().out)
    assert "sensors" not in out
    assert len(out["failed_sensors"]) == 1


@respx.mock
def test_sensors_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        sensors([], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().err


@respx.mock
def test_sensors_network_failure_exits_nonzero(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        sensors([], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


def test_sensors_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        sensors([])
    assert exc_info.value.code == 1


# -- notifications ---------------------------------------------------------------------


@respx.mock
def test_notifications_success(settings, notifications_payload, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/notification/system").mock(
        return_value=httpx.Response(200, json=notifications_payload)
    )
    notifications([], settings)
    out = json.loads(capsys.readouterr().out)
    assert out == ["Planned downtime 2026-06-20 02:00-03:00 UTC"]


@respx.mock
def test_notifications_empty_not_an_error(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/notification/system").mock(return_value=httpx.Response(204))
    notifications([], settings)
    assert json.loads(capsys.readouterr().out) == []


@respx.mock
def test_notifications_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        notifications([], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().err


@respx.mock
def test_notifications_network_failure_exits_nonzero(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/notification/system").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(SystemExit) as exc_info:
        notifications([], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


# -- fetch ---------------------------------------------------------------------


def _next_url(base_url: str, location: int, param) -> str:
    return f"{base_url}/LocationData/Next/{location}/{int(param)}/01/1"


@respx.mock
def test_fetch_single_page(settings, gas_batch, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_next_url(settings.base_url, 510, Param.GAS)).mock(
        side_effect=[httpx.Response(200, json=gas_batch), httpx.Response(204)]
    )
    fetch(["510", "gas"], settings)
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2


@respx.mock
def test_fetch_all_drains_batches(settings, gas_batch, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_next_url(settings.base_url, 510, Param.GAS)).mock(
        side_effect=[
            httpx.Response(200, json=gas_batch[:1]),
            httpx.Response(200, json=gas_batch[1:]),
            httpx.Response(204),
        ]
    )
    fetch(["510", "gas", "--all"], settings)
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2


@respx.mock
def test_fetch_empty_not_an_error(settings, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_next_url(settings.base_url, 510, Param.GAS)).mock(return_value=httpx.Response(204))
    fetch(["510", "gas"], settings)
    assert json.loads(capsys.readouterr().out) == []


def test_fetch_invalid_param_exits_2(settings):
    with pytest.raises(SystemExit) as exc_info:
        fetch(["510", "bogus"], settings)
    assert exc_info.value.code == 2


@respx.mock
def test_fetch_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        fetch(["510", "gas"], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().err


@respx.mock
def test_fetch_network_failure_exits_nonzero(settings, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_next_url(settings.base_url, 510, Param.GAS)).mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(SystemExit) as exc_info:
        fetch(["510", "gas"], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


# -- repeat ---------------------------------------------------------------------


def _repeat_url(base_url: str, location: int, param) -> str:
    return f"{base_url}/LocationData/Repeat/{location}/{int(param)}/01"


@respx.mock
def test_repeat_success(settings, gas_batch, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_repeat_url(settings.base_url, 510, Param.GAS)).mock(
        return_value=httpx.Response(200, json=gas_batch)
    )
    repeat(["510", "gas"], settings)
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2


@respx.mock
def test_repeat_no_previous_batch_not_an_error(settings, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_repeat_url(settings.base_url, 510, Param.GAS)).mock(return_value=httpx.Response(204))
    repeat(["510", "gas"], settings)
    assert json.loads(capsys.readouterr().out) == []


@respx.mock
def test_repeat_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        repeat(["510", "gas"], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().err


@respx.mock
def test_repeat_network_failure_exits_nonzero(settings, capsys):
    from aqmesh_client.models import Param

    _mock_auth(settings.base_url)
    respx.get(_repeat_url(settings.base_url, 510, Param.GAS)).mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(SystemExit) as exc_info:
        repeat(["510", "gas"], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().err


def test_repeat_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        repeat(["510", "gas"])
    assert exc_info.value.code == 1


# -- main routing ---------------------------------------------------------------------


def test_main_no_args_exits_2(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])
    assert exc_info.value.code == 2


def test_main_unknown_command_exits_2(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["bogus"])
    assert exc_info.value.code == 2
    assert "Unknown command" in capsys.readouterr().err


@respx.mock
def test_main_routes_ping(settings, serverping_payload, capsys, monkeypatch):
    monkeypatch.setattr("aqmesh_client.cli.APISettings", lambda **_: settings)
    respx.get(f"{settings.base_url}/serverping").mock(
        return_value=httpx.Response(200, json=serverping_payload)
    )
    cli.main(["ping"])
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == "Vn 0.9"
