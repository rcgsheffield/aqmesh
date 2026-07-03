"""Raw JSON batch validation against bundled JSON Schemas.

Schema drift (the vendor API adding, removing, or retyping a field) is the
primary risk this module guards against.  We validate only the most recent
file per (location, param) — schema changes affect all files uniformly, so
one representative file per batch is sufficient to detect them without
iterating over the entire raw store.
"""

from __future__ import annotations

import json
import logging
from importlib.resources import files
from pathlib import Path

import jsonschema

from .models import Param

logger = logging.getLogger(__name__)


def load_schema(param: Param) -> dict:
    """Return the bundled JSON Schema dict for *param*."""
    schema_ref = files("aqmesh_pipeline.schemas") / f"raw_{param.label}_reading.json"
    return json.loads(schema_ref.read_text(encoding="utf-8"))


def validate_raw_file(path: Path, schema: dict) -> list[dict]:
    """Validate every record in a raw JSON batch file against *schema*.

    Returns a list of error dicts ``{record_index, message, path}``; an empty
    list means every record passed.  Errors are collected rather than raised so
    a single bad record does not abort the rest of the batch.
    """
    records = json.loads(path.read_bytes())
    if not isinstance(records, list):
        return [
            {
                "record_index": -1,
                "message": f"Expected JSON array, got {type(records).__name__}",
                "path": [],
            }
        ]
    errors: list[dict] = []
    for i, record in enumerate(records):
        try:
            jsonschema.validate(record, schema)
        except jsonschema.ValidationError as exc:
            errors.append(
                {
                    "record_index": i,
                    "message": exc.message,
                    "path": list(exc.absolute_path),
                }
            )
    return errors
