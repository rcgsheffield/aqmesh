"""Tests for cleaning: sentinel handling and calibration scaling."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from aqmesh_pipeline.models import Param
from aqmesh_pipeline.transform import clean_readings, resample_5min


def test_clean_gas_applies_slope_and_offset(gas_batch):
    cleaned = clean_readings(pd.DataFrame(gas_batch), Param.GAS)

    # value = prescaled * slope + offset
    expected = 444.39 * 1.0574 - 76.2663
    assert cleaned.loc[0, "co"] == pytest.approx(expected)
    # A valid slightly-negative reading is preserved (not treated as missing).
    assert cleaned.loc[0, "so2"] == pytest.approx(-1.09)


def test_clean_gas_blanks_sentinels(gas_batch):
    cleaned = clean_readings(pd.DataFrame(gas_batch), Param.GAS)
    # -999 (stabilizing) and -1000 (not fitted) become NaN.
    assert math.isnan(cleaned.loc[0, "no2"])
    assert math.isnan(cleaned.loc[0, "h2s"])


def test_clean_gas_sorted_and_has_metadata(gas_batch):
    cleaned = clean_readings(pd.DataFrame(gas_batch), Param.GAS)
    assert list(cleaned["reading_number"]) == [3256954, 3256955]
    assert pd.api.types.is_datetime64_any_dtype(cleaned["reading_datestamp"])
    assert "temperature_c" in cleaned.columns
    assert "temperature_f" in cleaned.columns


def test_clean_particle(particle_batch):
    cleaned = clean_readings(pd.DataFrame(particle_batch), Param.PARTICLE)
    assert cleaned.loc[0, "pm2_5"] == pytest.approx(0.17)
    assert math.isnan(cleaned.loc[0, "pm1"])  # -1000 sentinel
    assert cleaned.loc[0, "reading_status"] == "OK"
    # Both temperature columns always emitted; temperature_c absent from fixture → NA.
    assert "temperature_c" in cleaned.columns
    assert pd.isna(cleaned.loc[0, "temperature_c"])
    assert "temperature_f" in cleaned.columns


def test_clean_empty_returns_empty():
    out = clean_readings(pd.DataFrame(), Param.GAS)
    assert out.empty


def test_resample_5min_is_deferred(gas_batch):
    with pytest.raises(NotImplementedError):
        resample_5min(pd.DataFrame(gas_batch))
