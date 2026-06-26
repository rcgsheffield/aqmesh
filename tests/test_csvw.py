"""Tests for the W3C CSVW descriptor builder (issue #92)."""

from __future__ import annotations

import json

from aqmesh_pipeline.csvw import COLUMN_DATATYPES, build_csvw

_GENERATED_AT_WITH_MICROS = "2026-06-19T09:30:00.123456+00:00"

_METADATA = {
    "dataset": "AQMesh cleaned readings",
    "param": "gas",
    "location_number": 510,
    "row_count": 2,
    "provenance": {
        "location_name": "Sheffield City Centre",
        "latitude": 53.38,
        "longitude": -1.48,
        "pod_serial_number": "2410149",
        "firmware_version": "v3.22",
        "environment": "test",
        "source": "AQMesh API",
        "generated_at": _GENERATED_AT_WITH_MICROS,
    },
    "processing": {
        "calibrated": True,
        "formula": "value = prescaled * slope + offset",
        "sentinel_handling": "fault/redaction sentinels converted to missing (NaN)",
    },
    "columns": {
        "location_number": {
            "description": "AQMesh location (site) identifier",
            "units": None,
            "calibrated": False,
        },
        "reading_datestamp": {
            "description": "Timestamp of the reading",
            "units": None,
            "calibrated": False,
        },
        "co": {"description": "Carbon monoxide", "units": "ppb", "calibrated": True},
        "pm2_5": {
            "description": "Particulate matter <2.5 µm",
            "units": "ug/m3",
            "calibrated": True,
        },
        "reading_status": {
            "description": "Pod reading status",
            "units": None,
            "calibrated": False,
        },
    },
    "reading_status_legend": {},
}


def test_build_csvw_top_level_fields():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")

    assert doc["@context"] == "http://www.w3.org/ns/csvw"
    assert doc["@type"] == "Table"
    assert doc["url"] == "aqmesh_510_gas.csv"
    assert doc["dc:title"] == "AQMesh cleaned readings — gas — location 510"
    assert doc["dc:source"] == "AQMesh API"
    assert "dcat:spatial" in doc
    assert doc["dcat:spatial"]["geo:lat"] == 53.38
    assert doc["dcat:spatial"]["geo:long"] == -1.48
    assert "tableSchema" in doc


def test_build_csvw_omits_spatial_when_coords_none():
    meta = {
        **_METADATA,
        "provenance": {**_METADATA["provenance"], "latitude": None, "longitude": None},
    }
    doc = build_csvw(meta, "aqmesh_510_gas.csv")
    assert "dcat:spatial" not in doc


def test_build_csvw_omits_spatial_when_only_one_coord():
    for missing in ("latitude", "longitude"):
        meta = {
            **_METADATA,
            "provenance": {**_METADATA["provenance"], missing: None},
        }
        doc = build_csvw(meta, "aqmesh_510_gas.csv")
        assert "dcat:spatial" not in doc, f"dcat:spatial present when {missing!r} is None"


def test_build_csvw_column_datatypes():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    cols = {c["name"]: c for c in doc["tableSchema"]["columns"]}

    assert cols["reading_datestamp"]["datatype"] == COLUMN_DATATYPES["reading_datestamp"]
    assert cols["location_number"]["datatype"] == "integer"
    assert cols["co"]["datatype"] == "number"
    assert cols["reading_status"]["datatype"] == "string"


def test_build_csvw_unit_code_omitted_when_none():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    cols = {c["name"]: c for c in doc["tableSchema"]["columns"]}

    assert "schema:unitCode" not in cols["reading_datestamp"]
    assert "schema:unitCode" not in cols["location_number"]
    assert cols["co"]["schema:unitCode"] == "ppb"
    assert cols["pm2_5"]["schema:unitCode"] == "ug/m3"


def test_build_csvw_column_order_matches_metadata():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    csvw_names = [c["name"] for c in doc["tableSchema"]["columns"]]
    assert csvw_names == list(_METADATA["columns"].keys())


def test_build_csvw_dc_modified_strips_microseconds():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    assert "." not in doc["dc:modified"]
    assert doc["dc:modified"].startswith("2026-06-19T09:30:00")


def test_build_csvw_location_none_fallback():
    meta = {**_METADATA, "location_number": None}
    doc = build_csvw(meta, "aqmesh_510_gas.csv")
    assert "unknown" in doc["dc:title"]
    assert "None" not in doc["dc:title"]


def test_build_csvw_dc_description_content():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    desc = doc["dc:description"]
    assert "Calibrated readings" in desc
    assert "sentinels" in desc.lower()


def test_build_csvw_unicode_roundtrips():
    doc = build_csvw(_METADATA, "aqmesh_510_gas.csv")
    serialised = json.dumps(doc, ensure_ascii=False)
    assert "µm" in serialised
    assert "\\u00b5" not in serialised
