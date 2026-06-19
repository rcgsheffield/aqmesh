# AQMesh API reference

A curated, agent- and human-readable distillation of the vendor manual
**`AQMesh-API-instructions-V2.18.pdf`** (kept in the repo root). The PDF is the
authoritative source; this set extracts the parts the pipeline cares about —
endpoint paths, parameters, and response shapes — without the manual's large
example-data dumps.

Each page links to the others and to the code that calls the endpoint, so you
can jump between "what the API offers" and "where we use it".

## Pages

| Page | Covers | Manual §§ |
| --- | --- | --- |
| [`authentication.md`](authentication.md) | Token exchange, lifetime, and data-ownership scoping | 4.1, 4.2 |
| [`readings.md`](readings.md) | The cursor `Next`/`Repeat` loop, `Param`/`Units`/`TPC`/`Version` segments, and obscured-value sentinels | 4.10, 4.11, 4.12 |
| [`assets.md`](assets.md) | `Assets_V1` — the pod/location inventory that drives the download loop | 4.19 (4.3 obsolete) |
| [`diagnostics.md`](diagnostics.md) | Read-only health & context: server ping, system notifications, failed sensors, sensor details | 4.16, 4.17, 4.8, 4.20 |
| [`device-management.md`](device-management.md) | Pod/sensor **write** operations — frequencies, rebase, restabilise (the pipeline deliberately does **not** call these) | 4.4, 4.5, 4.6, 4.7, 4.9, 4.18 |

## Base URLs

Selected by `AQMESH_ENVIRONMENT` (see [`config.py`](../../src/aqmesh_pipeline/config.py)). Manual § 1.3.

| Environment | Base URL |
| --- | --- |
| `test` (default) | `https://apitest.aqmeshdata.net/api` |
| `prod` | `https://api.aqmeshdata.net/api` |

## What the pipeline uses

The HTTP client lives in [`client.py`](../../src/aqmesh_pipeline/client.py); the CLI
that exposes these to operators is [`cli.py`](../../src/aqmesh_pipeline/cli.py).

| Endpoint | Method + path | Used by |
| --- | --- | --- |
| Authenticate (4.1) | `POST /Authenticate` | every call — `AQMeshClient.authenticate` |
| Assets_V1 (4.19) | `GET /Pods/Assets_V1` | `ingest`, `check` — `get_assets` |
| LocationData/Next (4.10) | `GET /LocationData/Next/{loc}/{param}/{units}/{tpc}[/{version}]` | `ingest` — `iter_location_data` |
| LocationData/Repeat (4.11) | `GET /LocationData/Repeat/{loc}/{param}/{units}[/{version}]` | `aqmesh repeat` — `repeat_last` |
| Server ping (4.16) | `GET /serverping` | `aqmesh ping`, `check` — `server_ping` |
| System notifications (4.17) | `GET /notification/system` | `check` — `get_system_notifications` |
| Failed sensors (4.8) | `GET /Pods/SensorFail` | `aqmesh sensors` — `get_failed_sensors` |
| Sensor details (4.20) | `GET /sensor/SensorDetail//{active}` | `aqmesh sensors` — `get_sensor_details` |

Everything else in the manual is either reference material (example payloads in
4.13–4.15) or device-mutating operations we intentionally leave to the AQMesh web
portal — see [`device-management.md`](device-management.md) for why.
