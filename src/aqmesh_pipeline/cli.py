"""Command-line entrypoint to run flows locally without a Prefect server.

Usage::

    aqmesh pipeline   # ingest + clean (default)
    aqmesh ingest     # download raw data only
    aqmesh clean      # rebuild cleaned CSVs from the raw store
    aqmesh check      # smoke-test: authenticate and list pods (no writes)
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from .client import AQMeshAuthError, AQMeshClient
from .config import Settings, get_settings
from .flows.clean import clean_data
from .flows.ingest import ingest_raw
from .flows.pipeline import pipeline


def check(settings: Settings | None = None) -> None:
    """Smoke-test connectivity: load settings, authenticate, and list pods.

    Read-only — downloads no readings and writes nothing to disk. Exits non-zero
    (``SystemExit(1)``) on any failure so it is usable in scripts and CI.
    """
    if settings is None:
        try:
            settings = get_settings()
        except ValidationError as exc:
            print(
                "Missing or invalid credentials — set AQMESH_USERNAME and "
                "AQMESH_PASSWORD (see .env.example).\n"
                f"{exc}"
            )
            raise SystemExit(1) from exc

    print(
        f"Checking AQMesh API ({settings.environment}) at {settings.base_url} "
        f"as {settings.username} ..."
    )
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            assets = client.get_assets()
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}")
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}")
        raise SystemExit(1) from exc

    print(f"OK — authenticated, {len(assets)} asset(s) visible.")
    for asset in assets[:10]:
        name = asset.location_name or "(unnamed)"
        print(f"  location {asset.location_number}: {name} [serial {asset.serial_number}]")
    if len(assets) > 10:
        print(f"  ... and {len(assets) - 10} more.")


_COMMANDS = {
    "pipeline": pipeline,
    "ingest": ingest_raw,
    "clean": clean_data,
    "check": check,
}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="aqmesh", description="AQMesh data pipeline.")
    parser.add_argument(
        "command",
        nargs="?",
        default="pipeline",
        choices=_COMMANDS.keys(),
        help="Which flow to run (default: pipeline).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    _COMMANDS[args.command]()


if __name__ == "__main__":
    main()
