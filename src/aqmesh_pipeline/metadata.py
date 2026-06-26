"""Build the sidecar data dictionary that documents each clean CSV (issue #58).

The clean CSVs carry no record of units, processing stage, or status-code meanings,
which is a reproducibility and data-sharing risk. For every CSV we write a sibling
``<name>.metadata.json`` describing each column (description, units, calibrated flag),
the processing applied, a ``reading_status`` legend, and per-run provenance.

Units for the calibrated gas species are read from the raw payload's ``<sp>_units``
field where present (the API reports them per species, e.g. ppb vs ppm), falling back
to the static table below. Particle channels and housekeeping columns have static units.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from .models import GAS_SPECIES, PARTICLE_CHANNELS, Asset, Param

if TYPE_CHECKING:
    from .config import Settings


#: Human-readable description for each output column.
COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Identity / base columns.
    "location_number": "AQMesh location (site) identifier",
    "pod_serial_number": "Serial number of the pod that produced the reading",
    "reading_number": "Per-location/param sequence number of the reading",
    "reading_datestamp": "Timestamp of the reading",
    # Gas species (calibrated concentrations).
    "co": "Carbon monoxide",
    "no": "Nitric oxide",
    "so2": "Sulfur dioxide",
    "no2": "Nitrogen dioxide",
    "o3": "Ozone",
    "h2s": "Hydrogen sulfide",
    "eo": "Ethylene oxide",
    # Particulate channels (calibrated).
    "pm1": "Particulate matter <1 µm",
    "pm2_5": "Particulate matter <2.5 µm",
    "pm4": "Particulate matter <4 µm",
    "pm10": "Particulate matter <10 µm",
    "pm_tpc": "Total particle concentration (all size fractions)",
    "pm_total": "Total particulate matter",
    # Environmental / housekeeping passthrough columns.
    "temperature_f": "Air temperature",
    "pressure": "Atmospheric pressure",
    "humidity": "Relative humidity",
    "battery_voltage": "Pod battery voltage",
    "super_cap_voltage": "Super-capacitor voltage",
    "reading_status": "Pod reading status",
}

#: Units known statically (independent of the raw payload).
STATIC_UNITS: dict[str, str | None] = {
    "pm1": "ug/m3",
    "pm2_5": "ug/m3",
    "pm4": "ug/m3",
    "pm10": "ug/m3",
    "pm_tpc": "ug/m3",
    "pm_total": "ug/m3",
    "temperature_f": "degF",
    "pressure": "mbar",
    "humidity": "%",
    "battery_voltage": "V",
    "super_cap_voltage": "V",
}

#: Columns produced by calibration (``prescaled * slope + offset``). All other
#: columns are passed through or are identity columns.
CALIBRATED_COLUMNS: frozenset[str] = frozenset(GAS_SPECIES) | frozenset(PARTICLE_CHANNELS)

#: Meaning of the ``reading_status`` string values.
#: Applies to particle readings only (API §4.12). Source: API instructions v2.17.
READING_STATUS_LEGEND: dict[str, str] = {
    "OK": "Reading nominal — no issue detected",
    "Deliquescence": (
        "Outlying values due to hygroscopic particle size growth (high humidity); "
        "readings are available but should be treated as potentially unreliable"
    ),
    "Misread": (
        "Particle or noise sensor unable to transfer valid data; affected values are set to missing"
    ),
    "Other Fault Zero": (
        "Particle counter unable to provide a valid reading following a power-cycle "
        "or settings change; affected values are set to missing"
    ),
}


def extract_species_units(raw_df: pd.DataFrame, species: tuple[str, ...]) -> dict[str, str]:
    """Read per-species units from the raw payload's ``<sp>_units`` fields.

    For each species present, take the first non-null ``<sp>_units`` value. Species
    whose units column is absent or all-null are omitted (the caller falls back to
    :data:`STATIC_UNITS`).
    """
    units: dict[str, str] = {}
    for sp in species:
        col = f"{sp}_units"
        if col not in raw_df.columns:
            continue
        non_null = raw_df[col].dropna()
        if not non_null.empty:
            units[sp] = str(non_null.iloc[0])
    return units


def build_metadata(
    cleaned_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    param: Param,
    asset: Asset | None,
    settings: Settings,
    generated_at: datetime,
) -> dict:
    """Assemble the sidecar data dictionary for one cleaned CSV.

    The ``columns`` block is built from ``cleaned_df.columns`` so it always matches
    the columns actually written. Gas units come from the raw payload where present
    (see :func:`extract_species_units`); everything else uses :data:`STATIC_UNITS`.
    ``asset`` may be ``None`` (no persisted asset snapshot) -> provenance falls back
    to whatever the cleaned frame carries.
    """
    species_units = extract_species_units(raw_df, GAS_SPECIES) if param is Param.GAS else {}

    columns: dict[str, dict] = {}
    for col in cleaned_df.columns:
        units = species_units.get(col, STATIC_UNITS.get(col))
        columns[col] = {
            "description": COLUMN_DESCRIPTIONS.get(col, col),
            "units": units,
            "calibrated": col in CALIBRATED_COLUMNS,
        }

    location_number = int(asset.location_number) if asset else None
    if location_number is None and "location_number" in cleaned_df.columns:
        first = cleaned_df["location_number"].dropna()
        location_number = int(first.iloc[0]) if not first.empty else None

    return {
        "dataset": "AQMesh cleaned readings",
        "param": param.label,
        "location_number": location_number,
        "row_count": int(len(cleaned_df)),
        "provenance": {
            "location_name": asset.location_name if asset else None,
            "latitude": asset.location_latitude if asset else None,
            "longitude": asset.location_longitude if asset else None,
            "pod_serial_number": asset.serial_number if asset else None,
            "firmware_version": asset.firmware_version if asset else None,
            "environment": settings.environment,
            "source": "AQMesh API",
            "generated_at": generated_at.isoformat(),
        },
        "processing": {
            "calibrated": True,
            "formula": "value = prescaled * slope + offset",
            "sentinel_handling": "fault/redaction sentinels converted to missing (NaN)",
        },
        "columns": columns,
        "reading_status_legend": READING_STATUS_LEGEND,
    }
