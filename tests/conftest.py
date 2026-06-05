"""Shared pytest fixtures: a Settings pointing at a temp data root, plus sample
API payloads modelled on the manual's examples (sections 4.13, 4.15, 4.19)."""

from __future__ import annotations

import os
import tempfile

# Isolate Prefect from any developer/CI config and run flows against an in-process
# ephemeral API backed by a throwaway SQLite DB. Set BEFORE importing prefect so
# the settings are picked up at import time. (The packaged temporary-server
# harness is unreachable under WSL2; in-process ephemeral mode works reliably.)
_PREFECT_HOME = tempfile.mkdtemp(prefix="aqmesh-prefect-test-")
os.environ.update(
    PREFECT_HOME=_PREFECT_HOME,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE="true",
    PREFECT_API_DATABASE_CONNECTION_URL=f"sqlite+aiosqlite:///{_PREFECT_HOME}/test.db",
    # Quiet flow-run logging (and the noisy "stopping temporary server" line that
    # the ephemeral server otherwise writes to an already-closed stream at exit).
    PREFECT_LOGGING_LEVEL="CRITICAL",
)
os.environ.pop("PREFECT_API_URL", None)

import pytest  # noqa: E402

from aqmesh_pipeline.config import Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        username="test-user",
        password="test-pass",
        environment="test",
        data_root=tmp_path,
        max_retries=2,
    )


@pytest.fixture
def assets_payload() -> list[dict]:
    return [
        {"location_number": 510, "serial_number": 2410149, "firmware_version": "v3.22"},
        {"location_number": 915, "serial_number": 2410103, "firmware_version": "v5.6"},
    ]


@pytest.fixture
def gas_batch() -> list[dict]:
    """Two gas readings: a normal one, a 'not fitted' sensor, and a sentinel."""
    base = {
        "location_number": 510,
        "pod_serial_number": 2410149,
        "reading_datestamp": "2019-04-19T09:15:00",
        "co_state": "Reading",
        "co_prescaled": 444.39,
        "co_slope": 1.0574,
        "co_offset": -76.2663,
        # so2 is a valid (slightly negative) reading, not a sentinel.
        "so2_state": "Reading",
        "so2_prescaled": -1.09,
        "so2_slope": 1.0,
        "so2_offset": 0.0,
        # no2 is stabilizing -> sentinel -999.
        "no2_state": "Stabilizing",
        "no2_prescaled": -999,
        "no2_slope": 1.0,
        "no2_offset": 0.0,
        # h2s not fitted -> sentinel -1000 with null calibration.
        "h2s_state": "Not Fitted",
        "h2s_prescaled": -1000.00,
        "h2s_slope": None,
        "h2s_offset": None,
        "temperature_f": 54.7,
        "pressure": 1024.5,
        "humidity": 69.5,
    }
    first = {**base, "gas_reading_number": 3256954}
    second = {
        **base,
        "gas_reading_number": 3256955,
        "reading_datestamp": "2019-04-19T09:30:00",
        "co_prescaled": 484.49,
    }
    return [first, second]


@pytest.fixture
def seed_raw(settings, gas_batch, particle_batch):
    """Populate the raw store for location 510 (gas + particle) and return settings."""
    from aqmesh_pipeline.models import Param
    from aqmesh_pipeline.storage import write_raw_batch

    write_raw_batch(settings, 510, Param.GAS, gas_batch, pulled_at="20260101T000000Z", seq=0)
    write_raw_batch(
        settings, 510, Param.PARTICLE, particle_batch, pulled_at="20260101T000000Z", seq=0
    )
    return settings


@pytest.fixture
def particle_batch() -> list[dict]:
    return [
        {
            "particle_reading_number": 15622255,
            "location_number": 510,
            "pod_serial_number": 2410149,
            "reading_datestamp": "2019-03-09T16:11:00",
            "reading_status": "OK",
            "pm2_5_prescale": 0.17,
            "pm2_5_slope": 1.0,
            "pm2_5_offset": 0.0,
            "pm10_prescale": 0.17,
            "pm10_slope": 1.0,
            "pm10_offset": 0.0,
            # pm1 reported as not-fitted sentinel.
            "pm1_prescale": -1000,
            "pm1_slope": 1.0,
            "pm1_offset": 0.0,
            "temperature_f": 52.16,
            "humidity": 50.3,
        }
    ]
