# Assets — the pod/location inventory

Manual § 4.19. Implemented in
[`AQMeshClient.get_assets`](../../src/aqmesh_pipeline/client.py); modelled by
[`Asset`](../../src/aqmesh_pipeline/models.py).

```
GET /Pods/Assets_V1
```

Returns every pod/location visible to the authenticated user (subject to
[ownership checks](authentication.md#data-ownership-checks-42)). This list drives
the per-`(location, param)` download loop in the `ingest` flow, and is what
[`aqmesh check`](../../src/aqmesh_pipeline/cli.py) prints.

> **Use `Assets_V1`, not the obsolete `GET /Pods/Assets` (4.3).** `Assets_V1`
> adds the combined `Pod_P2` (averaging period) and `Pod_P3` (transmission
> interval) used by newer (V5.0+) firmware.

## Fields the pipeline relies on

The full payload is wide (~40 fields) and varies by firmware, so the model keeps
`extra="allow"` and pins only what we depend on:

| Field | Why it matters |
| --- | --- |
| `location_number` | Primary key for the download loop and storage partitions |
| `location_name` | Display only |
| `serial_number` | Pod serial; display / cross-reference with [sensor details](diagnostics.md) |
| `firmware_version` | e.g. `v3.22`, `v5.6` — determines frequency model (see [device-management](device-management.md)) |
| `last_gas_reading_number`, `last_particle_reading_number` | Last reading IDs the server holds for the pod |
| `location_latitude`, `location_longitude` | Siting (often null on the test fleet) |

Other notable fields in the raw payload include `pod_latitude/longitude`,
`project_name`, `customer_name`, `owner_name`, `last_connection`,
`gps_status_description`, and the `gas_p1/p2/p3` / `particle_p1/p2/p3` sampling
parameters. Access any of them via attribute or `model_extra` since extras are
preserved.

---

Next: [authentication](authentication.md) · [readings](readings.md) · [diagnostics](diagnostics.md)
