[![CI](https://github.com/rcgsheffield/aqmesh/actions/workflows/ci.yml/badge.svg)](https://github.com/rcgsheffield/aqmesh/actions/workflows/ci.yml)

# AQMesh Data Pipeline

Outdoor air quality sensors data pipeline for the [AQMesh](https://www.aqmesh.com) platform.

It downloads all raw readings from the AQMesh API to a shared storage volume and cleans them into
research-ready CSV. Orchestrated with [Prefect 3](https://docs.prefect.io/v3/get-started).

## How it works

1. **Ingest** (`aqmesh-ingest-raw`): authenticate, list pods via `/Pods/Assets_V1`, then for each
   location loop the cursor-style `/LocationData/Next/...` endpoint until exhausted. Each batch is
   written to the raw store immediately (append-only) so an interruption never loses data.
2. **Clean** (`aqmesh-clean`): read all raw readings per location (deduping rebased values by reading
   number), convert fault/redaction sentinels (`-999`, `-1000`, …) to missing, apply calibration
   (`value = prescaled × slope + offset`), and write one CSV per location/param.

The parent flow `aqmesh-pipeline` runs ingest then clean, scheduled hourly.

### Data layout (under `AQMESH_DATA_ROOT`)

```
raw/   location=<n>/param=<gas|particle>/<pulled_at>_<seq>.json   # exact API payloads, append-only
clean/ location=<n>/aqmesh_<n>_<param>.csv                        # scaled, sentinels blanked
state/ pointers.json                                              # progress per location/param
```

> **Note:** 5-minute time-bucket resampling is scaffolded but not yet implemented
> (`transform.resample_5min`). The pipeline currently produces cleaned per-reading data.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync                       # create venv + install deps
cp .env.example .env          # then fill in AQMESH_USERNAME / AQMESH_PASSWORD
uv run ruff check .           # lint
uv run pytest                 # tests

# Run flows locally without a Prefect server (uses the test API by default):
uv run aqmesh ingest          # download raw data only
uv run aqmesh clean           # rebuild CSVs from the raw store
uv run aqmesh pipeline        # ingest + clean (default)
```

Configuration is environment-driven (see `.env.example`); set `AQMESH_ENVIRONMENT=test` to target
`apitest.aqmeshdata.net` or `prod` for `api.aqmeshdata.net`.

## Production deployment (Ubuntu 24.04 VPS)

Self-hosted Prefect server + worker, managed by systemd. From a checkout on the VM:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

See **[docs/deployment.md](docs/deployment.md)** for the full deployment and verification guide.

## Generative AI usage

Parts of this repository were written with AI assistance under human direction. See
[AI-STATEMENT.md](AI-STATEMENT.md) for details.
