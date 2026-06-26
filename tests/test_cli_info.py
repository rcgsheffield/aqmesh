"""Tests for the read-only context commands `aqmesh ping` and `aqmesh sensors`."""

from __future__ import annotations

import httpx
import pytest
import respx

from aqmesh_pipeline import cli
from aqmesh_pipeline.cli import _sensors_cmd, ping

# -- ping --------------------------------------------------------------------


@respx.mock
def test_ping_success(settings, serverping_payload, capsys):
    # No /Authenticate route — ping must not need credentials.
    respx.get(f"{settings.base_url}/serverping").mock(
        return_value=httpx.Response(200, json=serverping_payload)
    )
    ping(settings)
    out = capsys.readouterr().out
    assert "server version Vn 0.9" in out
    assert "most recent reading" in out
    assert "2026-06-19T08:57:00" in out


@respx.mock
def test_ping_unreachable_exits_nonzero(settings, capsys):
    respx.get(f"{settings.base_url}/serverping").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        ping(settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().out


@respx.mock
def test_ping_works_without_credentials(monkeypatch, tmp_path, serverping_payload, capsys):
    # No AQMESH_USERNAME/PASSWORD set: ping falls back to environment-only settings.
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.delenv("AQMESH_ENVIRONMENT", raising=False)
    monkeypatch.chdir(tmp_path)  # avoid picking up a real .env
    base = "https://apitest.aqmeshdata.net/api"  # test environment default
    respx.get(f"{base}/serverping").mock(return_value=httpx.Response(200, json=serverping_payload))
    ping()  # loads settings without credentials
    assert "server version" in capsys.readouterr().out


# -- sensors -----------------------------------------------------------------


def _mock_auth(base_url):
    respx.post(f"{base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )


@respx.mock
def test_sensors_success(settings, sensor_detail_payload, failed_sensor_payload, capsys):
    _mock_auth(settings.base_url)
    respx.get(url__regex=rf"{settings.base_url}/sensor/SensorDetail.*").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload)
    )
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    _sensors_cmd([], settings)
    out = capsys.readouterr().out
    assert "2 sensor(s) reported" in out
    assert "O3" in out
    assert "replace" in out  # the flagged O3 sensor
    assert "1 sensor(s) recommended for replacement" in out
    assert "1 failed sensor(s)" in out
    assert "SO2" in out


@respx.mock
def test_sensors_active_flag(settings, sensor_detail_payload, failed_sensor_payload):
    _mock_auth(settings.base_url)
    route = respx.get(url__regex=rf"{settings.base_url}/sensor/SensorDetail.*").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload)
    )
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    _sensors_cmd(["--active"], settings)
    assert route.calls.last.request.url.path.endswith("/sensor/SensorDetail//1")


@respx.mock
def test_sensors_failed_only_skips_inventory(settings, failed_sensor_payload, capsys):
    _mock_auth(settings.base_url)
    # No SensorDetail route registered: --failed-only must not call it.
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    _sensors_cmd(["--failed-only"], settings)
    out = capsys.readouterr().out
    assert "sensor(s) reported" not in out
    assert "1 failed sensor(s)" in out


@respx.mock
def test_sensors_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        _sensors_cmd([], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().out


@respx.mock
def test_sensors_network_failure_exits_nonzero(settings, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        _sensors_cmd([], settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().out


def test_sensors_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _sensors_cmd([])
    assert exc_info.value.code == 1


# -- main routing ------------------------------------------------------------


@respx.mock
def test_main_routes_sensors(settings, sensor_detail_payload, failed_sensor_payload, monkeypatch):
    monkeypatch.setattr("aqmesh_pipeline.cli.get_settings", lambda: settings)
    _mock_auth(settings.base_url)
    respx.get(url__regex=rf"{settings.base_url}/sensor/SensorDetail.*").mock(
        return_value=httpx.Response(200, json=sensor_detail_payload)
    )
    respx.get(f"{settings.base_url}/Pods/SensorFail").mock(
        return_value=httpx.Response(200, json=failed_sensor_payload)
    )
    cli.main(["sensors", "--failed-only"])  # routed via _ARGV_COMMANDS
