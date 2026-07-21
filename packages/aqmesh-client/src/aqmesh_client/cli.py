"""Standalone command-line interface for the ``aqmesh_client`` package.

Wraps the read-only AQMesh API methods so they can be exercised directly from a
shell, a notebook host, or a script — without installing the full pipeline
distribution (Prefect, pandas, etc). Every command prints JSON to stdout;
progress/error text goes to stderr, so stdout stays pipeable (e.g. to ``jq``).

Usage::

    aqmesh-client ping                    # server health/freshness (no credentials required)
    aqmesh-client assets                  # list pods/locations visible to this account
    aqmesh-client sensors                 # sensor status + failures (--active/--failed-only)
    aqmesh-client notifications           # operator notices
    aqmesh-client fetch <location> <gas|particle>   # one page of unread readings (--all to drain)
    aqmesh-client repeat <location> <gas|particle>  # re-fetch the last delivered batch

This is a client-inspection tool only — it never advances state that the
pipeline depends on for anything beyond the AQMesh server's own cursor, and it
has no confirmation-gated destructive commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from .client import AQMeshAuthError, AQMeshClient
from .config import APISettings
from .models import Param


def _resolve_settings(settings: APISettings | None) -> APISettings:
    """Return ``settings`` or load them from the environment, exiting 1 if credentials
    are missing or invalid."""
    if settings is not None:
        return settings
    try:
        return APISettings()
    except ValidationError as exc:
        print(
            "Missing or invalid credentials — set AQMESH_USERNAME and "
            f"AQMESH_PASSWORD (see .env.example).\n{exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _resolve_settings_optional(settings: APISettings | None) -> APISettings:
    """Like :func:`_resolve_settings`, but tolerate missing credentials.

    Used by ``ping``, which hits an unauthenticated endpoint — the environment
    still selects test vs prod, so a blank credential is harmless.
    """
    if settings is not None:
        return settings
    try:
        return APISettings()
    except ValidationError:
        return APISettings(username="", password="")  # type: ignore[call-arg]


def _emit(data: object, *, pretty: bool) -> None:
    print(json.dumps(data, indent=2 if pretty else None))


def _add_pretty(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print the JSON output (indent=2)."
    )


_PARAM_CHOICES = {"gas": Param.GAS, "particle": Param.PARTICLE}


def ping(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """Query the server health endpoint (manual 4.16). Needs no credentials."""
    parser = argparse.ArgumentParser(
        prog="aqmesh-client ping", description="Query AQMesh server health (no credentials)."
    )
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings_optional(settings)
    try:
        with AQMeshClient(settings) as client:
            snapshot = client.server_ping()
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _emit(snapshot.model_dump(mode="json"), pretty=args.pretty)


def assets(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """List pods/locations available to the authenticated account."""
    parser = argparse.ArgumentParser(
        prog="aqmesh-client assets", description="List pods/locations visible to this account."
    )
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            items = client.get_assets()
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _emit([item.model_dump(mode="json") for item in items], pretty=args.pretty)


def sensors(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """Report per-sensor status/age/expiry plus sensors that have failed."""
    parser = argparse.ArgumentParser(
        prog="aqmesh-client sensors",
        description="Report sensor status (manual 4.20) and failed sensors (4.8).",
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
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            failed = client.get_failed_sensors()
            details = None if args.failed_only else client.get_sensor_details(active=args.active)
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    result: dict[str, object] = {"failed_sensors": [f.model_dump(mode="json") for f in failed]}
    if details is not None:
        result["sensors"] = [d.model_dump(mode="json") for d in details]
    _emit(result, pretty=args.pretty)


def notifications(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """List operator notices (manual 4.17)."""
    parser = argparse.ArgumentParser(
        prog="aqmesh-client notifications", description="List AQMesh operator notices."
    )
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            notices = client.get_system_notifications()
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _emit(notices, pretty=args.pretty)


def fetch(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """Fetch unread readings for a location/param via the Next cursor (manual 4.10).

    Each page advances the server-side cursor, same as the pipeline's ``ingest``.
    """
    parser = argparse.ArgumentParser(
        prog="aqmesh-client fetch",
        description=(
            "Fetch unread readings for a location/param (manual 4.10). "
            "Advances the server-side cursor, same as the pipeline's ingest step."
        ),
    )
    parser.add_argument("location", type=int, help="Location number.")
    parser.add_argument("param", choices=sorted(_PARAM_CHOICES), help="Which param to fetch.")
    parser.add_argument(
        "--all", action="store_true", help="Drain every unread batch instead of just one page."
    )
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)
    param = _PARAM_CHOICES[args.param]
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            batches = client.iter_location_data(args.location, param)
            readings = [r for batch in batches for r in batch] if args.all else next(batches, [])
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _emit(readings, pretty=args.pretty)


def repeat(argv: Sequence[str], settings: APISettings | None = None) -> None:
    """Re-fetch the most recently delivered batch without advancing the cursor (manual 4.11)."""
    parser = argparse.ArgumentParser(
        prog="aqmesh-client repeat",
        description=(
            "Re-fetch the last delivered batch for a location/param (manual 4.11). "
            "Does not advance the server-side cursor."
        ),
    )
    parser.add_argument("location", type=int, help="Location number.")
    parser.add_argument("param", choices=sorted(_PARAM_CHOICES), help="Which param to re-fetch.")
    _add_pretty(parser)
    args = parser.parse_args(argv)

    settings = _resolve_settings(settings)
    param = _PARAM_CHOICES[args.param]
    try:
        with AQMeshClient(settings) as client:
            client.authenticate()
            readings = client.repeat_last(args.location, param)
    except AQMeshAuthError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Could not reach the AQMesh API at {settings.base_url}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _emit(readings, pretty=args.pretty)


_COMMANDS = {
    "ping": ping,
    "assets": assets,
    "sensors": sensors,
    "notifications": notifications,
    "fetch": fetch,
    "repeat": repeat,
}


def main(argv: Sequence[str] | None = None) -> None:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    if not argv_list:
        print(f"usage: aqmesh-client {{{','.join(_COMMANDS)}}} ...", file=sys.stderr)
        raise SystemExit(2)

    command, rest = argv_list[0], argv_list[1:]
    if command not in _COMMANDS:
        print(f"Unknown command: {command!r}. Choices: {', '.join(_COMMANDS)}", file=sys.stderr)
        raise SystemExit(2)
    _COMMANDS[command](rest)


if __name__ == "__main__":
    main()
