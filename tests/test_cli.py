"""Tests for the `aqmesh check` smoke-test command — all HTTP mocked."""

from __future__ import annotations

import httpx
import pytest
import respx

from aqmesh_pipeline.cli import check


@respx.mock
def test_check_success(settings, assets_payload, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get(f"{settings.base_url}/Pods/Assets_V1").mock(
        return_value=httpx.Response(200, json=assets_payload)
    )
    check(settings)  # should not raise
    out = capsys.readouterr().out
    assert "OK" in out
    assert "2 asset" in out
    assert "location 510" in out


@respx.mock
def test_check_auth_failure_exits_nonzero(settings, capsys):
    respx.post(f"{settings.base_url}/Authenticate").mock(
        return_value=httpx.Response(403, text="nope")
    )
    with pytest.raises(SystemExit) as exc_info:
        check(settings)
    assert exc_info.value.code == 1
    assert "Authentication failed" in capsys.readouterr().out
