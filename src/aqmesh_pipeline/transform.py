"""Clean raw AQMesh readings into a tidy, research-ready table.

Two cleaning steps are applied (manual sections 4.12-4.15):

1. **Sentinel handling** - reading values that encode a fault/redaction
   (e.g. ``-999`` stabilizing, ``-1000`` not fitted) are converted to missing.
2. **Calibration** - the delivered ``*_prescaled`` value is scaled to the final
   measurement via ``value = prescaled * slope + offset``.

The output is one tidy row per ``reading_datestamp`` with one column per pollutant.
:func:`resample_5min` optionally aggregates this onto a regular 5-minute grid.
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


#: Identity columns that are constant within one location/param frame and are
#: carried through resampling unchanged rather than averaged.
_IDENTITY_COLS = ("location_number", "pod_serial_number")


def _join_distinct(values: pd.Series) -> object:
    """Join the distinct non-null values in a bin into a single ``;``-separated string.

    Used to aggregate non-numeric columns (e.g. ``reading_status``) that cannot be
    averaged. Returns ``NaN`` for an empty bin so it reads the same as an empty
    numeric bin.
    """
    distinct = values.dropna().unique()
    if len(distinct) == 0:
        return float("nan")
    return ";".join(sorted(str(v) for v in distinct))


def resample_5min(df: pd.DataFrame, freq: str = "5min") -> pd.DataFrame:
    """Resample a cleaned location/param frame onto a regular time grid.

    Expects the output of :func:`clean_readings` for a single pod: a frame with a
    ``reading_datestamp`` column and one column per pollutant. Every column is
    carried through -- nothing is filtered out, so researchers can decide what to
    work with. Within each ``freq`` bucket, numeric columns are averaged (the
    bucket value is the **mean** of the readings it contains, ignoring missing
    values) and non-numeric columns (e.g. ``reading_status``) are aggregated to the
    ``;``-joined distinct values seen in the bucket. Buckets that contain no
    readings become ``NaN`` -- there is no forward-fill. Buckets are aligned to
    wall-clock marks (00:00, 00:05, ... for the default 5-minute grid).

    ``location_number`` and ``pod_serial_number`` are constant within the frame and
    are preserved as leading columns (keeping their original dtype rather than being
    coerced to a float average).

    Args:
        df: Cleaned readings for one location/param, as returned by
            :func:`clean_readings`.
        freq: A pandas offset alias for the bucket width (default ``"5min"``).

    Returns:
        A frame with one row per ``freq`` bucket from the first to the last
        reading, carrying every (aggregated) column. Empty in -> empty out.
    """
    if df.empty:
        return df

    identity = {col: df[col].iloc[0] for col in _IDENTITY_COLS if col in df.columns}
    indexed = df.set_index("reading_datestamp").sort_index()

    agg = {
        col: ("mean" if pd.api.types.is_numeric_dtype(indexed[col]) else _join_distinct)
        for col in indexed.columns
        if col not in _IDENTITY_COLS
    }
    resampled = indexed.resample(freq).agg(agg)

    for offset, (col, value) in enumerate(identity.items()):
        resampled.insert(offset, col, value)
    return resampled.reset_index()
