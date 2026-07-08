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

from aqmesh_client.models import GAS_SPECIES, PARTICLE_CHANNELS, Asset, Param

from . import __version__
from .storage import raw_param_dir

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


#: GitHub raw URL prefix for schema refs in the data-volume descriptor.
_SCHEMA_BASE = "https://raw.githubusercontent.com/rcgsheffield/aqmesh/main/schemas"


def build_raw_store_descriptor(
    assets: dict[int, Asset],
    pointers: dict,
    summaries: list[dict],
    settings: Settings,
    generated_at: datetime,
) -> dict:
    """Build the Frictionless Data Package descriptor for the raw store (issue #69).

    Written to ``data/raw/datapackage.yaml`` at the end of every ingest run so
    the data volume is self-describing even when shared without the repo.
    One resource entry per (location, param) partition.
    """
    summary_index = {(s["location_number"], s["param"]): s for s in summaries}

    resources = []
    for loc_str in sorted(pointers, key=lambda k: int(k)):
        loc_num = int(loc_str)
        asset = assets.get(loc_num)
        loc_name = asset.location_name if asset else None

        for param in list(Param):
            ptr = pointers[loc_str].get(param.label)
            if ptr is None:
                continue

            param_dir = raw_param_dir(settings, loc_num, param)
            file_count = len(list(param_dir.glob("*.json"))) if param_dir.exists() else 0

            title = f"Raw {param.label} readings – location {loc_num}"
            if loc_name:
                title += f" ({loc_name})"

            resource: dict = {
                "name": f"raw-{param.label}-{loc_num}",
                "title": title,
                "description": (
                    f"{param.label.capitalize()}-parameter batch files for location {loc_num}. "
                    f"Path pattern: location={loc_num}/param={param.label}/<pulled_at>_<seq>.json"
                ),
                "mediatype": "application/json",
                "schema": {"$ref": f"{_SCHEMA_BASE}/raw_{param.label}_reading.json"},
                "location_number": loc_num,
                "location_name": loc_name,
                "serial_number": asset.serial_number if asset else None,
                "firmware_version": asset.firmware_version if asset else None,
                "latitude": asset.location_latitude if asset else None,
                "longitude": asset.location_longitude if asset else None,
                "file_count": file_count,
                "last_reading_number": ptr.get("last_reading_number"),
                "last_datestamp": ptr.get("last_datestamp"),
            }

            summary = summary_index.get((loc_num, param.label))
            if summary:
                resource["status_this_run"] = summary["status"]
                resource["new_readings_this_run"] = summary["new_readings"]

            resources.append(resource)

    return {
        "name": "aqmesh-raw",
        "title": "AQMesh raw air-quality readings",
        "description": (
            "Append-only JSON batches from the AQMesh Data Platform API, one file per "
            "pull, partitioned by location and parameter type. Files are never modified "
            "after writing; cleaning and calibration happen downstream. "
            "Calibration formula: calibrated_value = prescale x slope + offset. "
            "Gas sentinels -1000 through -991; "
            "particle sentinels -1000, -893, -892 are converted to NaN during cleaning."
        ),
        "version": __version__,
        "licenses": [
            {
                "name": "OGL-UK-3.0",
                "title": "Open Government Licence 3.0",
                "path": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
            }
        ],
        "contributors": [
            {
                "title": "Joe Heffer",
                "email": "j.heffer@sheffield.ac.uk",
                "organization": "University of Sheffield",
                "role": "author",
            }
        ],
        "sources": [
            {
                "title": "AQMesh Data Platform API",
                "path": "https://www.aqmeshdata.net/",
            }
        ],
        "environment": settings.environment,
        "generated_at": generated_at.isoformat(),
        "resources": resources,
    }
