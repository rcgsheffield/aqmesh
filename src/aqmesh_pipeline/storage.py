"""Storage layout helpers for the shared data volume.

Layout under ``AQMESH_DATA_ROOT``::

    raw/   location=<n>/param=<gas|particle>/<pulled_at>_<seq>.json   # append-only payload
    clean/ location=<n>/aqmesh_<n>_<param>.csv                        # scaled, sentinels blanked
           location=<n>/aqmesh_<n>_<param>.metadata.json             # sidecar data dictionary
    state/ pointers.json                                             # progress per location/param
           assets.json                                              # asset snapshot for clean

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
from ruamel.yaml import YAML

from .config import Settings
from .models import Asset, Param

logger = logging.getLogger(__name__)

POINTERS_FILENAME = "pointers.json"
ASSETS_FILENAME = "assets.json"


# -- data-root docs ------------------------------------------------------
def write_data_docs(settings: Settings) -> list[Path]:
    """Copy all files from the bundled resources/ directory to the data root."""
    from importlib.resources import files

    resources = files("aqmesh_pipeline.resources")
    written = []
    for item in resources.iterdir():
        if item.is_file() and not item.name.startswith("_"):
            dest = settings.data_root / item.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest)
    return written


# -- path helpers --------------------------------------------------------
def raw_param_dir(settings: Settings, location_number: int, param: Param) -> Path:
    return settings.raw_dir / f"location={location_number}" / f"param={param.label}"


def clean_csv_path(settings: Settings, location_number: int, param: Param) -> Path:
    return (
        settings.clean_dir
        / f"location={location_number}"
        / f"aqmesh_{location_number}_{param.label}.csv"
    )


def resampled_csv_path(settings: Settings, location_number: int, param: Param) -> Path:
    return (
        settings.resampled_dir
        / f"location={location_number}"
        / f"aqmesh_{location_number}_{param.label}_daily.csv"
    )


def clean_metadata_path(settings: Settings, location_number: int, param: Param) -> Path:
    """Sidecar data-dictionary path sitting next to the clean CSV (issue #58)."""
    return clean_csv_path(settings, location_number, param).with_suffix(".metadata.json")


def clean_csvw_path(settings: Settings, location_number: int, param: Param) -> Path:
    """CSVW per-file descriptor path next to the clean CSV.

    Follows the W3C CSVW naming convention: ``<csv-url>-metadata.json``.
    """
    csv = clean_csv_path(settings, location_number, param)
    return csv.with_name(csv.name + "-metadata.json")


def raw_store_descriptor_path(settings: Settings) -> Path:
    """Frictionless datapackage descriptor for the entire raw store (issue #69)."""
    return settings.raw_dir / "datapackage.yaml"


def pointers_path(settings: Settings) -> Path:
    return settings.state_dir / POINTERS_FILENAME


def assets_path(settings: Settings) -> Path:
    return settings.state_dir / ASSETS_FILENAME


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


def read_raw_readings(settings: Settings, location_number: int, param: Param) -> pd.DataFrame:
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
def _write_json_atomic(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_clean_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    tmp.replace(path)


def write_clean_metadata(metadata: dict, path: Path) -> None:
    """Write the sidecar data dictionary for a clean CSV (issue #58)."""
    _write_json_atomic(metadata, path)


def write_clean_csvw(csvw: dict, path: Path) -> None:
    """Write the CSVW Table descriptor for a clean CSV."""
    _write_json_atomic(csvw, path)


def write_raw_store_descriptor(descriptor: dict, path: Path) -> None:
    """Write the Frictionless datapackage descriptor for the raw store atomically (issue #69)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    yaml = YAML()
    yaml.default_flow_style = False
    with tmp.open("w", encoding="utf-8") as f:
        yaml.dump(descriptor, f)
    tmp.replace(path)


# -- clean store ---------------------------------------------------------
def write_location_info(settings: Settings, asset_data: dict) -> Path:
    """Write asset+sensor metadata to clean/location=<n>/info.json."""
    dir_ = settings.clean_dir / f"location={asset_data['location_number']}"
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / "info.json"
    tmp = path.with_name("info.json.tmp")
    tmp.write_text(json.dumps(asset_data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


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


# -- state / assets snapshot ---------------------------------------------
def save_assets(settings: Settings, assets: list[Asset]) -> None:
    """Persist the asset list from ingest so the offline clean stage can read it.

    The clean stage never calls the API, so location provenance (name, coordinates,
    firmware) is snapshotted here during ingest and loaded back during cleaning.
    """
    path = assets_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [a.model_dump(mode="json") for a in assets]
    # Atomic-ish write to avoid corrupting state on interruption.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_assets(settings: Settings) -> dict[int, Asset]:
    """Load the persisted asset snapshot, keyed by location_number. Empty if absent."""
    path = assets_path(settings)
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {a.location_number: a for a in (Asset(**r) for r in records)}


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
