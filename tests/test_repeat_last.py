"""Tests for `aqmesh repeat-last` — all HTTP mocked."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from aqmesh_pipeline import cli
from aqmesh_pipeline.cli import _repeat_last_cmd
from aqmesh_pipeline.models import Param
from aqmesh_pipeline.storage import load_pointers, raw_param_dir, save_pointers

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _mock_auth(base_url: str) -> None:
    respx.post(f"{base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )


def _mock_repeat(base_url: str, location: int, param: Param, batch: list[dict]) -> None:
    # Default settings: units="01", version=0 → no version segment
    url = f"{base_url}/LocationData/Repeat/{location}/{int(param)}/01"
    respx.get(url).mock(return_value=httpx.Response(200, json=batch))


def _mock_repeat_204(base_url: str, location: int, param: Param) -> None:
    url = f"{base_url}/LocationData/Repeat/{location}/{int(param)}/01"
    respx.get(url).mock(return_value=httpx.Response(204))


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------


@respx.mock
def test_dry_run_no_api_calls(settings, capsys):
    # No routes registered — any unexpected HTTP call would raise.
    _repeat_last_cmd(["--location", "510", "--dry-run"], settings)
    out = capsys.readouterr().out
    assert "Dry run" in out


@respx.mock
def test_dry_run_both_params(settings, capsys):
    _repeat_last_cmd(["--location", "510", "--dry-run"], settings)
    out = capsys.readouterr().out
    assert "gas" in out
    assert "particle" in out
    assert "2 cursor" in out


@respx.mock
def test_dry_run_single_param(settings, capsys):
    _repeat_last_cmd(["--location", "510", "--param", "gas", "--dry-run"], settings)
    out = capsys.readouterr().out
    assert "gas" in out
    assert "particle" not in out


def test_dry_run_no_credentials_needed(monkeypatch, capsys):
    # --dry-run should succeed without any env vars / settings configured.
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    _repeat_last_cmd(["--location", "510", "--dry-run"])
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "510" in out


def test_dry_run_all_no_credentials_needed(monkeypatch, capsys):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    _repeat_last_cmd(["--all", "--dry-run", "--yes"])
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "ALL" in out


# ---------------------------------------------------------------------------
# successful re-fetch
# ---------------------------------------------------------------------------


@respx.mock
def test_repeat_location_gas_success(settings, gas_batch, capsys):
    _mock_auth(settings.base_url)
    _mock_repeat(settings.base_url, 510, Param.GAS, gas_batch)
    _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"], settings)
    out = capsys.readouterr().out
    assert "re-fetched 2 reading(s)" in out
    # Raw file should have been written.
    raw_dir = raw_param_dir(settings, 510, Param.GAS)
    files = list(raw_dir.glob("*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())
    assert len(written) == 2


@respx.mock
def test_repeat_location_both_params(settings, gas_batch, particle_batch, capsys):
    _mock_auth(settings.base_url)
    _mock_repeat(settings.base_url, 510, Param.GAS, gas_batch)
    _mock_repeat(settings.base_url, 510, Param.PARTICLE, particle_batch)
    _repeat_last_cmd(["--location", "510", "--yes"], settings)
    out = capsys.readouterr().out
    assert "location 510 gas: re-fetched" in out
    assert "location 510 particle: re-fetched" in out


@respx.mock
def test_repeat_all_with_yes(settings, assets_payload, gas_batch, particle_batch, capsys):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    # assets_payload has 2 locations (510, 915) × 2 params = 4 pairs
    for loc in (510, 915):
        _mock_repeat(settings.base_url, loc, Param.GAS, gas_batch)
        _mock_repeat(settings.base_url, loc, Param.PARTICLE, particle_batch)
    _repeat_last_cmd(["--all", "--yes"], settings)
    out = capsys.readouterr().out
    assert "4 batch(es) re-fetched" in out


# ---------------------------------------------------------------------------
# confirmation gate
# ---------------------------------------------------------------------------


@respx.mock
def test_repeat_all_yes_flag_skips_prompt(settings, assets_payload, gas_batch, particle_batch):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for loc in (510, 915):
        _mock_repeat(settings.base_url, loc, Param.GAS, gas_batch)
        _mock_repeat(settings.base_url, loc, Param.PARTICLE, particle_batch)
    # Should not prompt — runs cleanly.
    _repeat_last_cmd(["--all", "--yes"], settings)


@respx.mock
def test_repeat_all_prompts_yes_accepted(
    settings, assets_payload, gas_batch, particle_batch, monkeypatch, capsys
):
    _mock_auth(settings.base_url)
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    for loc in (510, 915):
        _mock_repeat(settings.base_url, loc, Param.GAS, gas_batch)
        _mock_repeat(settings.base_url, loc, Param.PARTICLE, particle_batch)
    monkeypatch.setattr("builtins.input", lambda _: "YES")
    _repeat_last_cmd(["--all"], settings)
    assert "4 batch(es) re-fetched" in capsys.readouterr().out


def test_repeat_all_prompts_not_yes_aborts(settings, monkeypatch, capsys):
    # Confirmation gate runs before any API call, so no mocks needed.
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--all"], settings)
    assert exc_info.value.code == 1
    assert "Aborted" in capsys.readouterr().out


@respx.mock
def test_production_warning_accepted(settings, gas_batch, monkeypatch, capsys):
    prod_settings = settings.model_copy(update={"environment": "prod"})
    _mock_auth(prod_settings.base_url)
    url = f"{prod_settings.base_url}/LocationData/Repeat/510/1/01"
    respx.get(url).mock(return_value=httpx.Response(200, json=gas_batch))
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _repeat_last_cmd(["--location", "510", "--param", "gas"], prod_settings)
    assert "re-fetched" in capsys.readouterr().out


@respx.mock
def test_production_warning_rejected(settings, monkeypatch, capsys):
    prod_settings = settings.model_copy(update={"environment": "prod"})
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--location", "510", "--param", "gas"], prod_settings)
    assert exc_info.value.code == 1
    assert "Aborted" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


@respx.mock
def test_empty_response_does_not_write_file(settings, capsys):
    _mock_auth(settings.base_url)
    _mock_repeat_204(settings.base_url, 510, Param.GAS)
    _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"], settings)
    out = capsys.readouterr().out
    assert "no data" in out
    raw_dir = raw_param_dir(settings, 510, Param.GAS)
    assert not list(raw_dir.glob("*.json")) if raw_dir.exists() else True


@respx.mock
def test_pointers_json_not_modified(settings, gas_batch, capsys):
    pointers = {
        "510": {"gas": {"last_reading_number": 99, "last_datestamp": "x", "new_readings": 1}}
    }
    save_pointers(settings, pointers)
    _mock_auth(settings.base_url)
    _mock_repeat(settings.base_url, 510, Param.GAS, gas_batch)
    _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"], settings)
    reloaded = load_pointers(settings)
    assert reloaded == pointers


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


@respx.mock
def test_api_failure_exits_nonzero(settings, capsys):
    _mock_auth(settings.base_url)
    url = f"{settings.base_url}/LocationData/Repeat/510/1/01"
    respx.get(url).mock(return_value=httpx.Response(500))
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"], settings)
    assert exc_info.value.code == 1
    assert "FAILED" in capsys.readouterr().out


@respx.mock
def test_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"], settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().out


def test_missing_credentials_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--location", "510", "--param", "gas", "--yes"])
    assert exc_info.value.code == 1


def test_param_and_all_mutually_exclusive(settings):
    with pytest.raises(SystemExit) as exc_info:
        _repeat_last_cmd(["--all", "--param", "gas"], settings)
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# main routing
# ---------------------------------------------------------------------------


@respx.mock
def test_main_routes_repeat_last(settings, monkeypatch, capsys):
    # Dry-run: no API calls, just verify the shim fires and parses correctly.
    monkeypatch.setattr("aqmesh_pipeline.cli.get_settings", lambda: settings)
    cli.main(["repeat-last", "--location", "510", "--dry-run"])
    out = capsys.readouterr().out
    assert "Dry run" in out
