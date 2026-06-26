"""Tests for the `aqmesh check` smoke-test command — all HTTP mocked."""

from __future__ import annotations

import httpx
import pytest
import respx

from aqmesh_pipeline import cli
from aqmesh_pipeline.cli import check


def _mock_health(base_url, serverping_payload, notifications_payload):
    """Register the best-effort health routes that the enriched ``check`` calls."""
    respx.get(f"{base_url}/serverping").mock(
        return_value=httpx.Response(200, json=serverping_payload)
    )
    respx.get(f"{base_url}/notification/system").mock(
        return_value=httpx.Response(200, json=notifications_payload)
    )


@respx.mock
def test_check_success(settings, assets_payload, serverping_payload, notifications_payload, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    _mock_health(settings.base_url, serverping_payload, notifications_payload)
    check(settings)  # should not raise
    out = capsys.readouterr().out
    assert "OK" in out
    assert "2 asset" in out
    assert "location 510" in out
    assert "server version Vn 0.9" in out  # health line from /serverping
    assert "Planned downtime" in out  # notice from /notification/system


@respx.mock
def test_check_tolerates_unavailable_health(settings, assets_payload, capsys):
    """A failing /serverping must not fail the whole check (best-effort)."""
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    respx.get(f"{settings.base_url}/serverping").mock(return_value=httpx.Response(404))
    respx.get(f"{settings.base_url}/notification/system").mock(return_value=httpx.Response(404))
    check(settings)  # should not raise despite health endpoints failing
    out = capsys.readouterr().out
    assert "OK" in out
    assert "unavailable" in out


@respx.mock
def test_check_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        check(settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().out


@respx.mock
def test_check_network_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SystemExit) as exc_info:
        check(settings)
    assert exc_info.value.code == 1
    assert "Could not reach" in capsys.readouterr().out


@respx.mock
def test_check_truncates_long_asset_list(
    settings, serverping_payload, notifications_payload, capsys
):
    many = [{"location_number": n, "serial_number": n} for n in range(11)]
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=many)
    )
    _mock_health(settings.base_url, serverping_payload, notifications_payload)
    check(settings)
    out = capsys.readouterr().out
    assert "11 asset" in out
    assert "and 1 more" in out  # only the first 10 are listed individually


def test_check_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)  # no local .env to supply credentials
    with pytest.raises(SystemExit) as exc_info:
        check()  # loads settings from the (empty) environment
    assert exc_info.value.code == 1


@pytest.mark.parametrize("command", ["pipeline", "ingest", "clean", "check", "ping"])
def test_main_routes_to_command(monkeypatch, command):
    called = []
    monkeypatch.setitem(cli._COMMANDS, command, lambda **kw: called.append(command))
    cli.main([command])
    assert called == [command]


def test_main_defaults_to_pipeline(monkeypatch):
    called = []
    monkeypatch.setitem(cli._COMMANDS, "pipeline", lambda **kw: called.append("pipeline"))
    cli.main([])  # no command -> default
    assert called == ["pipeline"]


@pytest.mark.parametrize("command", ["clean", "pipeline"])
def test_main_resample_flag_threaded(monkeypatch, command):
    seen = {}
    monkeypatch.setitem(cli._COMMANDS, command, lambda resample: seen.update(resample=resample))
    cli.main([command])
    assert seen == {"resample": True}  # on by default
    seen.clear()
    cli.main([command, "--no-resample"])
    assert seen == {"resample": False}


def test_main_rejects_unknown_command():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["nope"])
    assert exc_info.value.code == 2  # argparse usage error
