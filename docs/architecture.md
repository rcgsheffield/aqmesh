# Architecture

## Overview

The AQMesh pipeline downloads air quality readings from outdoor sensor pods via the AQMesh API,
stores them as append-only raw JSON, and produces cleaned, calibrated CSVs for researchers. It runs
as a pair of systemd services on a single Ubuntu VPS, orchestrated by a self-hosted Prefect 3
server on a 6-hourly schedule.

## Data flow

```
AQMesh API ──► client.py ──► flows/ingest.py ──► raw/   (append-only JSON)
                                                      │
                                                      ▼
                                         flows/clean.py ──► clean/ (calibrated CSVs)

Scheduled hourly at :06 (Europe/London) by Prefect 3
CLI: aqmesh pipeline | ingest | clean | check
```

## Source modules (`src/aqmesh_pipeline/`)

| Module | Responsibility |
| --- | --- |
| `config.py` | Pydantic settings loaded from environment (`.env`); defines `AQMESH_USERNAME`, `AQMESH_PASSWORD`, `AQMESH_ENVIRONMENT`, `AQMESH_DATA_ROOT` |
| `client.py` | AQMesh API client: bearer-token auth with auto-refresh, pod listing via `/Pods/Assets_V1`, cursor-style data iteration via `/LocationData/Next/…` |
| `models.py` | Data models and type definitions: `Param` enum (gas/particle), `Asset` (pod metadata), sentinel constants |
| `storage.py` | Raw store I/O — reading and writing JSON batches, CSVs, and the `state/pointers.json` cursor file |
| `transform.py` | Data cleaning: deduplication by reading number, sentinel → NaN conversion, calibration (`prescaled × slope + offset`) |
| `flows/ingest.py` | Prefect flow: authenticates, lists pods, downloads per-location/param data, writes to raw store |
| `flows/clean.py` | Prefect flow: reads all raw files per location, deduplicates, cleans, writes per-param CSVs |
| `flows/pipeline.py` | Parent Prefect flow: runs ingest then clean; registered as `aqmesh-pipeline/hourly` |
| `cli.py` | CLI entry point: `aqmesh pipeline \| ingest \| clean \| check` |

## Infrastructure

| Component | Role |
| --- | --- |
| `prefect-server` (systemd) | Prefect 3 API + web UI, SQLite backend, bound to `127.0.0.1:4200` |
| `prefect-worker` (systemd) | Polls `aqmesh-pool`, executes flow subprocesses; reads credentials from `.env` on start |
| `prefect.yaml` | Deployment definition: entrypoint, work pool (`aqmesh-pool`, type `process`), schedule |
| `deploy/bootstrap.sh` | Idempotent provisioning script — identical path for first install and rolling updates |

## Data layout (under `AQMESH_DATA_ROOT`)

```
raw/
  location=<n>/
    param=gas/
      <pulled_at>_<seq>.json        # exact API payloads, append-only
    param=particle/
      <pulled_at>_<seq>.json

clean/
  location=<n>/
    aqmesh_<n>_gas.csv              # scaled readings, sentinels → NaN
    aqmesh_<n>_particle.csv

resampled/
  location=<n>/
    aqmesh_<n>_gas_5min.csv         # clean readings averaged onto a 5-min grid
    aqmesh_<n>_particle_5min.csv

state/
  pointers.json                     # cursor per location/param pair — safe to restart mid-run
```

Raw files are never modified or deleted — the clean step always rebuilds from scratch.

## Design decisions

- **SQLite backend** — adequate for a single worker with no concurrent writers; known locking
  behaviour is non-fatal and documented in [`troubleshooting.md`](troubleshooting.md).
- **Append-only raw store** — an interrupted ingest run loses nothing; the next run resumes from
  `state/pointers.json` exactly where it left off.
- **Single idempotent deploy script** — `deploy/bootstrap.sh` is the update path as well as the
  install path, so there is no separate upgrade procedure.
- **5-minute resampling** — `transform.resample_5min` averages the cleaned per-reading data onto a
  regular 5-minute grid, written to the separate `resampled/` tree. Bins are aligned to wall-clock
  marks (00:00, 00:05, …); each bin value is the **mean** of the readings it contains (NaN within a
  bin is skipped, so sentinel-blanked values do not poison the average); bins containing no readings
  are left **NaN** with no forward-fill. The per-reading `clean/` CSVs are always produced as well,
  so raw cadence stays accessible. Resampling runs by default; `aqmesh clean --no-resample` (and
  `aqmesh pipeline --no-resample`) skips the `resampled/` output.
