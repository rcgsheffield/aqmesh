"""Command-line entrypoint to run flows locally without a Prefect server.

Usage::

    aqmesh pipeline   # ingest + clean (default)
    aqmesh ingest     # download raw data only
    aqmesh clean      # rebuild cleaned CSVs from the raw store
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from .flows.clean import clean_data
from .flows.ingest import ingest_raw
from .flows.pipeline import pipeline

_COMMANDS = {
    "pipeline": pipeline,
    "ingest": ingest_raw,
    "clean": clean_data,
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
