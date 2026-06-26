"""Build a W3C CSVW Table descriptor from the sidecar metadata dict.

The CSVW standard (https://www.w3.org/TR/tabular-data-primer/) requires a
``<csv>-metadata.json`` descriptor alongside each CSV for machine-readable
open-data publication. This module converts the existing ``.metadata.json``
sidecar produced by :mod:`aqmesh_pipeline.metadata` into the CSVW shape —
no information is gathered twice.
"""

from __future__ import annotations

from datetime import datetime

#: CSVW datatype for each well-known column.  Sensor reading columns not listed
#: here default to ``"number"``.
COLUMN_DATATYPES: dict[str, str | dict] = {
    "location_number": "integer",
    "pod_serial_number": "string",
    "reading_number": "integer",
    "reading_datestamp": {"base": "datetime", "format": "yyyy-MM-ddTHH:mm:ss"},
    "reading_status": "string",
}


def build_csvw(metadata: dict, csv_filename: str) -> dict:
    """Return a W3C CSVW Table descriptor for one cleaned CSV.

    Args:
        metadata:     The dict returned by :func:`aqmesh_pipeline.metadata.build_metadata`
                      for the same CSV.
        csv_filename: Bare filename only (e.g. ``"aqmesh_4973_gas.csv"``).
                      Used as the relative ``url`` within the descriptor.
    """
    prov = metadata["provenance"]
    processing = metadata["processing"]
    location_number = metadata.get("location_number")
    param = metadata.get("param", "")

    columns = []
    for name, col_info in metadata["columns"].items():
        col: dict = {
            "name": name,
            "titles": name,
            "dc:description": col_info["description"],
            "datatype": COLUMN_DATATYPES.get(name, "number"),
        }
        if col_info.get("units") is not None:
            col["schema:unitCode"] = col_info["units"]
        columns.append(col)

    desc_parts = []
    if processing.get("calibrated"):
        desc_parts.append(f"Calibrated readings ({processing['formula']}).")
    sentinel = processing.get("sentinel_handling", "")
    if sentinel:
        desc_parts.append(sentinel[0].upper() + sentinel[1:] + ".")
    dc_description = " ".join(desc_parts)

    dc_modified = datetime.fromisoformat(prov["generated_at"]).replace(microsecond=0).isoformat()

    title_loc = location_number if location_number is not None else "unknown"
    doc: dict = {
        "@context": [
            "http://www.w3.org/ns/csvw",
            {
                "dcat": "http://www.w3.org/ns/dcat#",
                "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
                "schema": "https://schema.org/",
            },
        ],
        "@type": "Table",
        "url": csv_filename,
        "dc:title": f"AQMesh cleaned readings — {param} — location {title_loc}",
        "dc:modified": dc_modified,
        "dc:source": prov["source"],
        "dc:description": dc_description,
    }

    lat = prov.get("latitude")
    lon = prov.get("longitude")
    if lat is not None and lon is not None:
        doc["dcat:spatial"] = {
            "@type": "dcat:Location",
            "geo:lat": lat,
            "geo:long": lon,
        }

    doc["tableSchema"] = {"columns": columns}
    return doc
