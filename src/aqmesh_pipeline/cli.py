"""Command-line entrypoint to run flows locally without a Prefect server.

Usage::

    aqmesh pipeline      # metadata + ingest + clean (default)
    aqmesh metadata      # sync location/sensor metadata; write info.json per pod
    aqmesh ingest        # download raw data only
    aqmesh clean         # rebuild cleaned CSVs from the raw store
    aqmesh check         # smoke-test: authenticate, list pods, server health (no writes)
    aqmesh ping          # server health/freshness probe (no credentials required)
    aqmesh sensors       # report sensor age/expiry/failures across the fleet (read-only)
    aqmesh repeat        # re-ingest the last delivered batch (does not advance cursor)

The ``clean`` and ``pipeline`` commands also write a daily resampled CSV per
location/param under ``resampled/`` by default; pass ``--no-resample`` to skip it.
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
from .flows.metadata import sync_location_metadata
from .flows.pipeline import pipeline
from .flows.validate import validate_raw_store
from .models import Param
from .storage import write_raw_batch


def _resolve_settings(settings: Settings | None) -> Settings:
    """Return ``settings`` or load them from the environment, exiting 1 if credentials
    are missing or invalid."""
    if settings is not None:
        return settings
    try:
        return get_settings()
    except ValidationError as exc:
        print(
            "Missing or invalid credentials — set AQMESH_USERNAME and "
            "AQMESH_PASSWORD (see .env.example).\n"
            f"{exc}"
        )
        raise SystemExit(1) from exc


def _resolve_settings_optional(settings: Settings | None) -> Settings:
    """Like :func:`_resolve_settings`, but tolerate missing credentials.

    Used by commands (``ping``) that hit unauthenticated endpoints — the
    environment still selects test vs prod, so a blank credential is harmless.
    """
    if settings is not None:
        return settings
    try:
        return get_settings()
    except ValidationError:
        return Settings(username="", password="")  # type: ignore[call-arg]


def check(settings: Settings | None = None) -> None:
    """Smoke-test connectivity: load settings, authenticate, list pods, report health.

    Read-only — downloads no readings and writes nothing to disk. Exits non-zero
    (``SystemExit(1)``) on any failure so it is usable in scripts and CI.
    """
    settings = _resolve_settings(settings)

    print(
        f"Checking AQMesh API ({settings.environment}) at {settings.base_url} "
        f"as {settings.username} ..."
    )
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            assets = client.get_assets()
            ping = _safe(lambda: client.server_ping())
            notices = _safe(lambda: client.get_system_notifications()) or []
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}")
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}")
        raise SystemExit(1) from exc

    print(f"OK — authenticated, {len(assets)} asset(s) visible.")
    if ping is not None:
        print(
            f"  server version {ping.version}; most recent reading "
            f"{ping.most_recent_reading}; last communication {ping.last_communication}"
        )
    for notice in notices:
        print(f"  notice: {notice}")
    for asset in assets[:10]:
        name = asset.location_name or "(unnamed)"
        print(f"  location {asset.location_number}: {name} [serial {asset.serial_number}]")
    if len(assets) > 10:
        print(f"  ... and {len(assets) - 10} more.")


def _safe(call):
    """Run ``call`` and return its result, or None if it raises an HTTP error.

    Lets ``check`` add best-effort health context without one optional endpoint
    failing the whole command.
    """
    try:
        return call()
    except httpx.HTTPError as exc:
        print(f"  (unavailable: {exc})")
        return None


def ping(settings: Settings | None = None) -> None:
    """Query the server health endpoint (manual 4.16) and print a freshness summary.

    Needs no credentials, so it answers "is the AQMesh server up and how fresh is
    its data?" independently of whether our account can authenticate. Exits non-zero
    if the server cannot be reached.
    """
    settings = _resolve_settings_optional(settings)
    print(f"Pinging AQMesh API ({settings.environment}) at {settings.base_url} ...")
    try:
        with AQMeshClient(settings) as client:
            snapshot = client.server_ping()
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}")
        raise SystemExit(1) from exc

    print(f"OK — server version {snapshot.version}")
    print(f"  server time:           {snapshot.server_time}")
    print(f"  most recent reading:   {snapshot.most_recent_reading}")
    print(f"  last communication:    {snapshot.last_communication}")
    print(f"  most recent processed: {snapshot.most_recent_processed}")


def _sensors_cmd(argv: Sequence[str], settings: Settings | None = None) -> None:
    """Report fleet sensor health: per-sensor age/expiry/replacement and failed sensors."""
    parser = argparse.ArgumentParser(
        prog="aqmesh sensors",
        description=(
            "Report pod sensor health across the fleet: per-sensor status, age, and "
            "expiry (manual 4.20) plus sensors that have tripped fail criteria (4.8). "
            "Read-only — makes no changes."
        ),
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="Only include active/installed pods (manual 4.20 Active=1). Default: all deployed.",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Show only the failed-sensors report, skipping the full sensor inventory.",
    )
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)

    print(f"Querying sensor health ({settings.environment}) at {settings.base_url} ...")
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            failed = client.get_failed_sensors()
            details = [] if args.failed_only else client.get_sensor_details(active=args.active)
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}")
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}")
        raise SystemExit(1) from exc

    if not args.failed_only:
        print(f"\n{len(details)} sensor(s) reported:")
        for d in details:
            flag = "  ⚠ replace" if d.replacement_needed else ""
            age = f"{d.age_in_months}mo" if d.age_in_months is not None else "?"
            print(
                f"  pod {d.serial_number} {d.sensor_type_name}: "
                f"{d.sensor_status_name}, age {age}, expires {d.expiry_date}{flag}"
            )
        flagged = [d for d in details if d.replacement_needed]
        if flagged:
            print(f"\n{len(flagged)} sensor(s) recommended for replacement.")

    print(f"\n{len(failed)} failed sensor(s):")
    for f in failed:
        print(
            f"  pod {f.pod_serial_number} {f.sensor_type} "
            f"(sensor {f.sensor_serial_number}): {f.fail_type} on {f.fail_date} — {f.status}"
        )


def _repeat_last_cmd(argv: Sequence[str], settings: Settings | None = None) -> None:
    """Parse repeat-last arguments and re-ingest the last delivered batch(es)."""
    parser = argparse.ArgumentParser(
        prog="aqmesh repeat",
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

    settings = _resolve_settings(settings)

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
    "metadata": sync_location_metadata,
    "ingest": ingest_raw,
    "clean": clean_data,
    "validate": validate_raw_store,
    "check": check,
    "ping": ping,
}

# Commands that take their own arguments and are dispatched before argparse.
_ARGV_COMMANDS = {
    "repeat": _repeat_last_cmd,
    "sensors": _sensors_cmd,
}


def main(argv: Sequence[str] | None = None) -> None:
    argv_list = list(argv) if argv is not None else sys.argv[1:]

    if argv_list and argv_list[0] in _ARGV_COMMANDS:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        _ARGV_COMMANDS[argv_list[0]](argv_list[1:])
        return

    parser = argparse.ArgumentParser(prog="aqmesh", description="AQMesh data pipeline.")
    parser.add_argument(
        "command",
        nargs="?",
        default="pipeline",
        choices=list(_COMMANDS.keys()),
        help="Which flow to run (default: pipeline).",
    )
    parser.add_argument(
        "--no-resample",
        action="store_true",
        help="Skip the daily resampled CSV output (clean/pipeline only).",
    )
    args = parser.parse_args(argv_list)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if args.command in ("clean", "pipeline"):
        _COMMANDS[args.command](resample=not args.no_resample)
    elif args.command == "validate":
        report = _COMMANDS["validate"]()
        if report.get("invalid", 0):
            raise SystemExit(1)
    else:
        _COMMANDS[args.command]()


if __name__ == "__main__":
    main()
