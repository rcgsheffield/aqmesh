"""Storage layout helpers for the shared data volume.

Layout under ``AQMESH_DATA_ROOT``::

    raw/   location=<n>/param=<gas|particle>/<pulled_at>_<seq>.json   # append-only payload
    clean/ location=<n>/aqmesh_<n>_<param>.csv                        # scaled, sentinels blanked
    state/ pointers.json                                             # progress per location/param

Raw files are append-only: every pull writes new files and nothing is ever
mutated. Cleaning reads *all* raw files for a location, ordered by pull time, and
dedupes by the reading number keeping the last occurrence -- so rebased values
(re-sent later with corrected numbers, manual 4.12) overwrite the originals.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .config import Settings
from .models import Param

logger = logging.getLogger(__name__)

POINTERS_FILENAME = "pointers.json"


# -- path helpers --------------------------------------------------------
def raw_param_dir(settings: Settings, location_number: int, param: Param) -> Path:
    return settings.raw_dir / f"location={location_number}" / f"param={param.label}"


def clean_csv_path(settings: Settings, location_number: int, param: Param) -> Path:
    return (
        settings.clean_dir
        / f"location={location_number}"
        / f"aqmesh_{location_number}_{param.label}.csv"
    )


def pointers_path(settings: Settings) -> Path:
    return settings.state_dir / POINTERS_FILENAME


# -- raw store -----------------------------------------------------------
def write_raw_batch(
    settings: Settings,
    location_number: int,
    param: Param,
    batch: list[dict],
    pulled_at: str,
    seq: int,
) -> Path:
    """Persist one reading batch exactly as received. Returns the file path."""
    out_dir = raw_param_dir(settings, location_number, param)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{pulled_at}_{seq:04d}.json"
    path.write_text(json.dumps(batch), encoding="utf-8")
    return path


def read_raw_readings(
    settings: Settings, location_number: int, param: Param
) -> pd.DataFrame:
    """Load and concatenate every raw reading for a location/param, deduped.

    Files are read in filename order (``<pulled_at>_<seq>``), which is
    chronological, so keeping the last occurrence of each reading number lets
    corrected (rebased) values win.
    """
    out_dir = raw_param_dir(settings, location_number, param)
    files = sorted(out_dir.glob("*.json"))
    if not files:
        return pd.DataFrame()

    records: list[dict] = []
    for f in files:
        records.extend(json.loads(f.read_text(encoding="utf-8")))
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    key = param.reading_number_field
    if key in df.columns:
        df = df.drop_duplicates(subset=key, keep="last").reset_index(drop=True)
    return df


# -- clean store ---------------------------------------------------------
def write_clean_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# -- state / pointers ----------------------------------------------------
def load_pointers(settings: Settings) -> dict:
    path = pointers_path(settings)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_pointers(settings: Settings, pointers: dict) -> None:
    path = pointers_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic-ish write to avoid corrupting state on interruption.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pointers, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def update_pointer(
    pointers: dict,
    location_number: int,
    param: Param,
    *,
    last_reading_number: int | None,
    last_datestamp: str | None,
    new_readings: int,
) -> None:
    """Record progress for a location/param in the in-memory pointers dict."""
    loc = pointers.setdefault(str(location_number), {})
    loc[param.label] = {
        "last_reading_number": last_reading_number,
        "last_datestamp": last_datestamp,
        "new_readings": new_readings,
    }
