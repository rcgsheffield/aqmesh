"""Tests for cleaning: sentinel handling and calibration scaling."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from aqmesh_pipeline.models import Param
from aqmesh_pipeline.transform import clean_readings, resample_daily


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
    assert cleaned["reading_datestamp"].dt.tz is not None  # always UTC-aware
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


def _cleaned_frame(rows: list[dict]) -> pd.DataFrame:
    """Build a cleaned-style frame (UTC-aware reading_datestamp) from row dicts."""
    df = pd.DataFrame(rows)
    df["reading_datestamp"] = pd.to_datetime(df["reading_datestamp"], utc=True)
    return df


def test_resample_daily_averages_within_bin():
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 1,
                "reading_datestamp": "2026-01-01T09:01:00",
                "co": 10.0,
            },
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 2,
                "reading_datestamp": "2026-01-01T14:30:00",
                "co": 20.0,
            },
        ]
    )
    out = resample_daily(df)
    assert len(out) == 1
    assert out.loc[0, "reading_datestamp"] == pd.Timestamp("2026-01-01", tz="UTC")
    assert out.loc[0, "co"] == pytest.approx(15.0)


def test_resample_daily_empty_bins_are_nan_and_midnight_aligned():
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 1,
                "reading_datestamp": "2026-01-01T09:02:00",
                "co": 10.0,
            },
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 2,
                "reading_datestamp": "2026-01-03T14:00:00",
                "co": 40.0,
            },
        ]
    )
    out = resample_daily(df).set_index("reading_datestamp")
    # Bins aligned to UTC midnight, spanning first to last reading.
    assert list(out.index) == [
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-01-02", tz="UTC"),
        pd.Timestamp("2026-01-03", tz="UTC"),
    ]
    assert out.loc["2026-01-01", "co"] == pytest.approx(10.0)
    # Day with no readings is NaN (no forward-fill).
    assert math.isnan(out.loc["2026-01-02", "co"])
    assert out.loc["2026-01-03", "co"] == pytest.approx(40.0)


def test_resample_daily_preserves_identity_keeps_all_columns():
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 1,
                "reading_datestamp": "2026-01-01T09:01:00",
                "co": 10.0,
                "reading_status": "OK",
            },
        ]
    )
    out = resample_daily(df)
    # Identity columns kept as their original value (not coerced to a float average).
    assert out.loc[0, "location_number"] == 510
    assert out.loc[0, "pod_serial_number"] == 2410149
    assert list(out.columns)[:3] == ["reading_datestamp", "location_number", "pod_serial_number"]
    # Nothing is filtered out: every other column is carried through too.
    assert "reading_number" in out.columns  # numeric -> averaged
    assert "co" in out.columns
    assert "reading_status" in out.columns  # non-numeric -> joined distinct


def test_resample_daily_joins_distinct_status_within_bin():
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 1,
                "reading_datestamp": "2026-01-01T09:01:00",
                "co": 10.0,
                "reading_status": "OK",
            },
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 2,
                "reading_datestamp": "2026-01-01T14:30:00",
                "co": 20.0,
                "reading_status": "FAULT",
            },
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 3,
                "reading_datestamp": "2026-01-03T09:00:00",
                "co": 30.0,
                "reading_status": "OK",
            },
        ]
    )
    out = resample_daily(df).set_index("reading_datestamp")
    # Non-numeric status is not averaged; distinct values in the bin are joined.
    assert out.loc["2026-01-01", "reading_status"] == "FAULT;OK"
    # An empty day reads as NaN for the status column too (no forward-fill).
    assert pd.isna(out.loc["2026-01-02", "reading_status"])


def test_resample_daily_skips_nan_within_bin():
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 1,
                "reading_datestamp": "2026-01-01T09:01:00",
                "co": float("nan"),
            },
            {
                "location_number": 510,
                "pod_serial_number": 2410149,
                "reading_number": 2,
                "reading_datestamp": "2026-01-01T14:30:00",
                "co": 20.0,
            },
        ]
    )
    out = resample_daily(df)
    # A sentinel-blanked reading does not poison the bucket mean.
    assert out.loc[0, "co"] == pytest.approx(20.0)


def test_resample_daily_empty_returns_empty():
    assert resample_daily(pd.DataFrame()).empty


def test_resample_daily_utc_alignment_across_dst():
    # Readings straddle the Europe/London spring-forward (2026-03-29 01:00 UTC,
    # clocks jump from 01:00 to 02:00 BST).  In local BST the second reading
    # appears at 03:30, which could naively be placed on a different wall-clock
    # day.  UTC bins must keep both readings in the same day (2026-03-29 UTC).
    df = _cleaned_frame(
        [
            {
                "location_number": 510,
                "pod_serial_number": 1,
                "reading_number": 1,
                "reading_datestamp": "2026-03-29T00:30:00+00:00",
                "co": 10.0,
            },
            {
                "location_number": 510,
                "pod_serial_number": 1,
                "reading_number": 2,
                "reading_datestamp": "2026-03-29T02:30:00+00:00",
                "co": 20.0,
            },
        ]
    )
    out = resample_daily(df)
    assert len(out) == 1
    assert out.loc[0, "reading_datestamp"] == pd.Timestamp("2026-03-29", tz="UTC")
    assert out.loc[0, "co"] == pytest.approx(15.0)
