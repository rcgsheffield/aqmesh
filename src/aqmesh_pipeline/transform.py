"""Clean raw AQMesh readings into a tidy, research-ready table.

Two cleaning steps are applied (manual sections 4.12-4.15):

1. **Sentinel handling** - reading values that encode a fault/redaction
   (e.g. ``-999`` stabilizing, ``-1000`` not fitted) are converted to missing.
2. **Calibration** - the delivered ``*_prescaled`` value is scaled to the final
   measurement via ``value = prescaled * slope + offset``.

The output is one tidy row per ``reading_datestamp`` with one column per pollutant.
5-minute resampling is intentionally deferred (see :func:`resample_5min`).
"""

from __future__ import annotations

import pandas as pd

from .models import (
    GAS_SENTINELS,
    GAS_SPECIES,
    PARTICLE_CHANNELS,
    PARTICLE_SENTINELS,
    Param,
)

# Environmental / housekeeping columns passed through unchanged when present.
_GAS_PASSTHROUGH = ("temperature_f", "pressure", "humidity", "battery_voltage")
_PARTICLE_PASSTHROUGH = (
    "temperature_f",
    "pressure",
    "humidity",
    "battery_voltage",
    "super_cap_voltage",
    "reading_status",
)


def _scale(
    prescaled: pd.Series,
    slope: pd.Series | None,
    offset: pd.Series | None,
    sentinels: frozenset[float],
) -> pd.Series:
    """Return ``prescaled * slope + offset`` with sentinel values blanked to NaN."""
    pre = pd.to_numeric(prescaled, errors="coerce")
    pre = pre.where(~pre.isin(sentinels))
    slope_n = pd.to_numeric(slope, errors="coerce") if slope is not None else 1.0
    offset_n = pd.to_numeric(offset, errors="coerce") if offset is not None else 0.0
    return pre * slope_n + offset_n


def _base_frame(df: pd.DataFrame, reading_number_field: str) -> pd.DataFrame:
    """Build the shared identity columns for a cleaned output frame.

    Args:
        df: Raw input DataFrame containing source columns.
        reading_number_field: Column name for the reading sequence number.

    Returns:
        A new DataFrame with location_number, pod_serial_number,
        reading_number, and reading_datestamp columns.
    """
    out = pd.DataFrame(index=df.index)
    out["location_number"] = df.get("location_number")
    out["pod_serial_number"] = df.get("pod_serial_number")
    out["reading_number"] = df.get(reading_number_field)
    out["reading_datestamp"] = pd.to_datetime(df.get("reading_datestamp"), errors="coerce")
    return out


def _append_passthrough(out: pd.DataFrame, df: pd.DataFrame, cols: tuple[str, ...]) -> None:
    """Append environmental passthrough columns from the source frame.

    Columns listed in ``cols`` are copied from ``df`` into ``out`` only
    when they are present in the source frame.

    Args:
        out: Output DataFrame to mutate in place.
        df: Source DataFrame to copy columns from.
        cols: Names of columns to pass through unchanged.
    """
    for col in cols:
        if col in df.columns:
            out[col] = df[col]


def clean_gas(df: pd.DataFrame) -> pd.DataFrame:
    """Apply sentinel handling and calibration to a raw gas readings frame.

    Args:
        df: Raw gas readings DataFrame as returned by the API.

    Returns:
        Tidy DataFrame with one row per reading_datestamp, sorted
        chronologically, with calibrated gas-species columns.
    """
    out = _base_frame(df, Param.GAS.reading_number_field)
    for sp in GAS_SPECIES:
        prescaled = f"{sp}_prescaled"
        if prescaled not in df.columns:
            continue
        out[sp] = _scale(
            df[prescaled], df.get(f"{sp}_slope"), df.get(f"{sp}_offset"), GAS_SENTINELS
        )
    _append_passthrough(out, df, _GAS_PASSTHROUGH)
    return out.sort_values("reading_datestamp").reset_index(drop=True)


def clean_particle(df: pd.DataFrame) -> pd.DataFrame:
    """Apply sentinel handling and calibration to a raw particle readings frame.

    Args:
        df: Raw particle readings DataFrame as returned by the API.

    Returns:
        Tidy DataFrame with one row per reading_datestamp, sorted
        chronologically, with calibrated particle-channel columns.
    """
    out = _base_frame(df, Param.PARTICLE.reading_number_field)
    for ch in PARTICLE_CHANNELS:
        prescale = f"{ch}_prescale"
        if prescale not in df.columns:
            continue
        out[ch] = _scale(
            df[prescale], df.get(f"{ch}_slope"), df.get(f"{ch}_offset"), PARTICLE_SENTINELS
        )
    _append_passthrough(out, df, _PARTICLE_PASSTHROUGH)
    return out.sort_values("reading_datestamp").reset_index(drop=True)


def clean_readings(df: pd.DataFrame, param: Param) -> pd.DataFrame:
    """Clean a raw reading frame for the given param. Empty in -> empty out."""
    if df.empty:
        return df
    return clean_gas(df) if param is Param.GAS else clean_particle(df)


def resample_5min(df: pd.DataFrame, freq: str = "5min") -> pd.DataFrame:  # noqa: ARG001
    """DEFERRED: resample cleaned readings onto regular 5-minute buckets.

    This is the planned next extension. The intended behaviour (to be confirmed
    with researchers): build a regular ``freq`` time index per pod, aggregate
    readings falling in each bucket (mean for concentrations), and mark empty
    buckets as missing. Not implemented yet -- the pipeline currently emits
    per-reading cleaned data only.
    """
    raise NotImplementedError(
        "5-minute resampling is deferred; see the project plan. "
        "Cleaned per-reading data is produced by clean_readings()."
    )
