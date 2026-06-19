# System requirements

VM sizing for running the AQMesh pipeline in production. For the provisioning steps themselves, see
[`deployment.md`](deployment.md).

## What runs on the VM

The pipeline is **not** a one-off batch script. Three things consume resources:

| Component | Lifetime | Notes |
| --- | --- | --- |
| `prefect-server` | Always on (24/7) | Prefect 3 server — uvicorn/Starlette API + SQLite, bound to `127.0.0.1:4200`. |
| `prefect-worker` | Always on (24/7) | Polls the `aqmesh-pool` work pool. |
| The flow run | Hourly, short-lived | Subprocess fired at 6 min past the hour; runs `ingest_raw()` → `clean_data()`, using pandas to dedupe and clean per-location data in memory, then exits. |

So the resident baseline is the always-on Prefect server + worker; the pandas memory use is a brief
hourly spike, not a constant load.

## Recommended specification

**1 vCPU · 4 GB RAM · 20 GB root disk · separate data volume on `/mnt/aqmesh`**, Ubuntu 24.04.

| Resource | Recommendation | Rationale |
| --- | --- | --- |
| **CPU** | 1 vCPU | The pipeline is single-threaded and I/O-bound (API polling + disk writes); there is no parallelism in the code. |
| **RAM** | 4 GB | The Prefect 3 server is the surprise cost: it sits at roughly several hundred MB idle, plus the worker, plus the hourly pandas subprocess. 2 GB can work but leaves little headroom and risks OOM as data-per-location grows. 4 GB is the comfortable spot. |
| **Root disk** | 20 GB | Enough for the OS, application code, and the `uv`-managed virtualenv. The pipeline data does **not** live here. |
| **Data volume** | Sized to retention (see below) | A separate volume mounted at `/mnt/aqmesh`; this is where unbounded growth happens. |
| **Network** | Outbound HTTPS only | To `api.aqmeshdata.net` (the AQMesh API) and `astral.sh` (uv install). No inbound exposure — the server binds to localhost. |

The University default Ubuntu box (1 core / 2 GB / 20 GB) is *almost* right — bump the RAM to 4 GB.
If, after go-live, the Prefect server plus the hourly pandas spike stay comfortably under ~2 GB in
practice, you could drop back to a 2 GB box, but don't start there.

## Data volume sizing

The growth is on the **data volume** (`/mnt/aqmesh`), not the root disk, and it is effectively
unbounded:

- `raw/` is **append-only and never pruned** — exact API JSON payloads, one file per pull-batch per
  location/param, every hour, indefinitely.
- `clean/` — CSV rewritten per location per run.
- The Prefect SQLite database also grows with flow-run history; Prefect does not auto-prune it by
  default.

Size the volume by `readings/hour × locations × retention period`. Start around **50–100 GB**,
monitor growth, and expand as needed.

## Open questions to confirm

Two things drive both the RAM spike and disk growth, and neither has a fixed value in the codebase —
confirm them before locking in a spec:

1. **How many pods/locations** will actually be ingested.
2. **Retention policy** — whether you want any pruning of the append-only `raw/` store or of
   Prefect's flow-run history. Without it, the data volume only ever grows.

## Scaling note

This sizing assumes the single-worker `process` pool described in [`deployment.md`](deployment.md),
backed by Prefect's default SQLite. Scaling beyond one worker requires PostgreSQL (and Redis) and a
correspondingly larger machine — out of scope here.
