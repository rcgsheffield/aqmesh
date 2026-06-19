"""Tests for Settings: environment URL selection, derived paths, and loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aqmesh_pipeline.config import BASE_URLS, Settings, get_settings


def test_base_url_selects_environment():
    test_s = Settings(username="u", password="p", environment="test")
    prod_s = Settings(username="u", password="p", environment="prod")
    assert test_s.base_url == BASE_URLS["test"]
    assert prod_s.base_url == BASE_URLS["prod"]


def test_derived_dirs_hang_off_data_root():
    s = Settings(username="u", password="p", data_root=Path("/data/aqmesh"))
    assert s.raw_dir == Path("/data/aqmesh/raw")
    assert s.clean_dir == Path("/data/aqmesh/clean")
    assert s.state_dir == Path("/data/aqmesh/state")


def test_get_settings_reads_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("AQMESH_USERNAME", "env-user")
    monkeypatch.setenv("AQMESH_PASSWORD", "env-pass")
    monkeypatch.setenv("AQMESH_DATA_ROOT", str(tmp_path))

    s = get_settings()
    assert s.username == "env-user"
    assert s.password.get_secret_value() == "env-pass"
    assert s.data_root == tmp_path


def test_skip_locations_parsed_from_env(monkeypatch):
    monkeypatch.setenv("AQMESH_USERNAME", "u")
    monkeypatch.setenv("AQMESH_PASSWORD", "p")
    monkeypatch.setenv("AQMESH_SKIP_LOCATIONS", "[4975, 4999]")
    s = get_settings()
    assert s.skip_locations == frozenset({4975, 4999})


def test_get_settings_missing_credentials_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("AQMESH_USERNAME", raising=False)
    monkeypatch.delenv("AQMESH_PASSWORD", raising=False)
    # Run from an empty dir so a developer's local .env can't supply credentials.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        get_settings()
