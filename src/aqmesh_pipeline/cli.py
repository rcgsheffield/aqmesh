"""Command-line entrypoint to run flows locally without a Prefect server.

Usage::

    aqmesh pipeline      # ingest + clean (default)
    aqmesh ingest        # download raw data only
    aqmesh clean         # rebuild cleaned CSVs from the raw store
    aqmesh check         # smoke-test: authenticate and list pods (no writes)
    aqmesh repeat-last   # re-ingest the last delivered batch (does not advance cursor)
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from .client import AQMeshAuthError, AQMeshClient
from .config import Settings, get_settings
from .flows.clean import clean_data
from .flows.ingest import ingest_raw
from .flows.pipeline import pipeline
from .models import Param
from .storage import write_raw_batch


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


def _repeat_last_cmd(argv: Sequence[str], settings: Settings | None = None) -> None:
    """Parse repeat-last arguments and re-ingest the last delivered batch(es)."""
    parser = argparse.ArgumentParser(
        prog="aqmesh repeat-last",
        description=(
            "Re-fetch the most recently delivered reading batch for one or more locations "
            "using the AQMesh Repeat endpoint (manual 4.11). "
            "The server-side cursor is NOT advanced — use 'aqmesh ingest' for normal polling."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--location",
        type=int,
        metavar="LOC",
        help="Location number to re-fetch.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Re-fetch the last batch for every location/param pair (requires --yes).",
    )
    parser.add_argument(
        "--param",
        choices=["gas", "particle"],
        help="Which param to re-fetch. Omit to re-fetch both (only valid with --location).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be re-fetched without making any API calls.",
    )
    args = parser.parse_args(argv)

    if args.all and args.param:
        parser.error("--param cannot be combined with --all.")

    # Pre-calculate pairs for --location (no credentials needed).
    # For --all, pairs are resolved later via get_assets() once authenticated.
    pairs: list[tuple[int, Param]] = []
    if not args.all:
        if args.param == "gas":
            loc_params: list[Param] = [Param.GAS]
        elif args.param == "particle":
            loc_params = [Param.PARTICLE]
        else:
            loc_params = list(Param)
        pairs = [(args.location, p) for p in loc_params]

    # Dry-run never makes API calls — exit before loading credentials.
    if args.dry_run:
        if not args.all:
            print(f"Will re-fetch last batch for {len(pairs)} cursor(s):")
            for location_number, param in pairs:
                print(f"  location {location_number}  {param.label}")
        else:
            print("Will re-fetch last batch for ALL locations.")
        print("Dry run — no API calls made.")
        return

    if settings is None:
        try:
            settings = get_settings()
        except ValidationError as exc:
            print(
                "Missing or invalid credentials — set AQMESH_USERNAME and "
                f"AQMESH_PASSWORD (see .env.example).\n{exc}"
            )
            raise SystemExit(1) from exc

    env_label = f"[{settings.environment.upper()}]"

    if not args.all:
        print(f"Will re-fetch last batch for {len(pairs)} cursor(s) {env_label}:")
        for location_number, param in pairs:
            print(f"  location {location_number}  {param.label}")

        if settings.environment == "prod" and not args.yes:
            answer = input(
                f"You are targeting the PRODUCTION environment ({settings.base_url}). "
                "Proceed? [y/N] "
            )
            if answer.strip().lower() != "y":
                print("Aborted.")
                raise SystemExit(1)
    else:
        # --all: confirm before making any API calls.
        print(f"Will re-fetch last batch for ALL locations {env_label}.")

        if not args.yes:
            answer = input(
                f"Re-fetch last batch for ALL locations {env_label}? "
                "This will write new raw files. Type YES to confirm: "
            )
            if answer.strip() != "YES":
                print("Aborted.")
                raise SystemExit(1)

    pulled_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    failures: list[tuple[int, Param, Exception]] = []

    with AQMeshClient(settings) as client:
        try:
            client.authenticate()
        except AQMeshAuthError as exc:
            print(f"Authentication failed: {exc}")
            raise SystemExit(1) from exc

        if args.all:
            # Resolve pairs now that we have an authenticated client.
            assets = client.get_assets()
            pairs = [(asset.location_number, p) for asset in assets for p in Param]
            if not pairs:
                print("No locations found.")
                return

        for seq, (location_number, param) in enumerate(pairs):
            try:
                batch = client.repeat_last(location_number, param)
                if batch:
                    write_raw_batch(
                        settings,
                        location_number,
                        param,
                        batch,
                        pulled_at=pulled_at,
                        seq=seq,
                    )
                    print(
                        f"  location {location_number} {param.label}: "
                        f"re-fetched {len(batch)} reading(s)"
                    )
                else:
                    print(
                        f"  location {location_number} {param.label}: "
                        "no data (server returned empty — no previous batch?)"
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append((location_number, param, exc))
                print(f"  location {location_number} {param.label}: FAILED — {exc}")

    if failures:
        print(f"\n{len(failures)} re-fetch(es) failed.")
        raise SystemExit(1)

    print(f"\nDone. {len(pairs)} batch(es) re-fetched.")
    print("Re-run 'aqmesh clean' to rebuild the cleaned CSVs from the updated raw store.")


_COMMANDS = {
    "pipeline": pipeline,
    "ingest": ingest_raw,
    "clean": clean_data,
    "check": check,
}


def main(argv: Sequence[str] | None = None) -> None:
    argv_list = list(argv) if argv is not None else sys.argv[1:]

    if argv_list and argv_list[0] == "repeat-last":
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        _repeat_last_cmd(argv_list[1:])
        return

    parser = argparse.ArgumentParser(prog="aqmesh", description="AQMesh data pipeline.")
    parser.add_argument(
        "command",
        nargs="?",
        default="pipeline",
        choices=_COMMANDS.keys(),
        help="Which flow to run (default: pipeline).",
    )
    args = parser.parse_args(argv_list)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    _COMMANDS[args.command]()


if __name__ == "__main__":
    main()
