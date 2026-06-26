# Readings: the cursor loop

Manual §§ 4.10, 4.11, 4.12. Implemented in
[`AQMeshClient.iter_location_data`](../../src/aqmesh_pipeline/client.py) and
`repeat_last`. Background on why the cursor is the source of truth:
[`pipeline.md`](../pipeline.md).

## LocationData/Next (4.10) — advance the cursor

```
GET /LocationData/Next/{Location_Number}/{Param}/{Units}/{TPC}/{Version}
```

Each call returns the next unread batch of readings for one `(location, param)`
pair **and advances a server-side pointer**. Loop until the server returns
`204 No Content` or an empty array. The cursor only advances on success, so an
interrupted run safely retries the failed pair next time.

> The route **rejects a trailing `/{Version}` segment** when version is the
> default `0`; the client appends the 5th segment only when `version` is non-zero.
> (Regression: issue #8.)

## LocationData/Repeat (4.11) — re-read without advancing

```
GET /LocationData/Repeat/{Location_Number}/{Param}/{Units}/{Version}
```

Returns **exactly the same data** as the most recent `Next` call for that pair,
without moving the pointer. Note there is **no `TPC` segment** here, unlike `Next`.
Exposed as [`aqmesh repeat`](../../src/aqmesh_pipeline/cli.py).

## Path segments

| Segment | Values | Notes |
| --- | --- | --- |
| `Param` | `1` = Gas, `2` = Particles | [`Param`](../../src/aqmesh_pipeline/models.py) enum |
| `Units` | 1st digit temp: `0` °C, `1` °F · 2nd digit: `0` ppb, `1` µg/m³ | e.g. `01` = °C + µg/m³ (electrolytic sensors only). Default `AQMESH_UNITS=01`. |
| `TPC` | `0` original, `1` include Total Particle Count | Particles only; count/cm³. Default `AQMESH_TPC=1`. `Next` only. |
| `Version` | `0` original, `1` include Ethylene Oxide | Omitted from the path when `0`. |

## Data conditions / obscured values (4.12)

The server **obscures readings it can't vouch for** by substituting sentinel
values rather than omitting the field. The cleaning step converts these to
missing (`NaN`). Defined as `GAS_SENTINELS` / `PARTICLE_SENTINELS` in
[`models.py`](../../src/aqmesh_pipeline/models.py):

| Param | Sentinels | Meaning |
| --- | --- | --- |
| Gas | `-1000, -999 … -991` | Not fitted (`-1000`) / rebasing / stabilising / other non-usable states |
| Particle | `-1000, -893, -892` | Not fitted / obscured |

Each sensor also carries a `<species>_state` (e.g. `"Reading"`, `"Stabilizing"`,
`"Not Fitted"`) describing why a value may be obscured.

## `reading_status` field (particle readings only)

Particle readings carry a `reading_status` string field separate from the numeric
sentinel mechanism above. All four observed values (confirmed against production
data and API instructions v2.17 §4.12):

| `reading_status` | Prescaled sentinel | Meaning |
| --- | --- | --- |
| `"OK"` | estimated reading | No issue detected |
| `"Deliquescence"` | estimated reading | Outlying values due to hygroscopic particle size growth at high humidity; readings available but potentially unreliable |
| `"Misread"` | `-893` | Particle or noise sensor unable to transfer valid data; values set to missing |
| `"Other Fault Zero"` | `-892` | Particle counter unable to provide a valid reading after a power-cycle or settings change; values set to missing |

The full legend is also embedded in the sidecar metadata JSON under `reading_status_legend`
(see [`metadata.py`](../../src/aqmesh_pipeline/metadata.py) `READING_STATUS_LEGEND`).

---

Next: [authentication](authentication.md) · [assets](assets.md) · [diagnostics](diagnostics.md)
