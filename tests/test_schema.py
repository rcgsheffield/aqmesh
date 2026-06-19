"""Validate test-fixture readings against the JSON Schema files in schemas/."""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text())


@pytest.fixture(scope="module")
def gas_schema():
    return load_schema("raw_gas_reading.json")


@pytest.fixture(scope="module")
def particle_schema():
    return load_schema("raw_particle_reading.json")


def test_gas_schema_valid(gas_schema, gas_batch):
    for reading in gas_batch:
        jsonschema.validate(instance=reading, schema=gas_schema)


def test_particle_schema_valid(particle_schema, particle_batch):
    for reading in particle_batch:
        jsonschema.validate(instance=reading, schema=particle_schema)
