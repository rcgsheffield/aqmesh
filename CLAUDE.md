# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                        # create venv + install all deps (including dev)
uv run ruff check .            # lint
uv run ruff check . --fix      # lint with auto-fix
uv run pytest                  # full test suite (coverage enforced ≥90%)
uv run pytest tests/test_flows.py  # single test file
uv run pytest -k test_ingest   # single test by name

# Run flows locally (no Prefect server needed; uses test API by default):
uv run aqmesh pipeline         # ingest + clean
uv run aqmesh ingest           # download raw data only
uv run aqmesh clean            # rebuild CSVs from raw store
uv run aqmesh check            # health check
```

Environment is configured via `.env` (copy from `.env.example`). Set `AQMESH_ENVIRONMENT=prod` to target the production API; default is `test` (`apitest.aqmeshdata.net`).

Pre-commit hooks keep `uv.lock` in sync — install once with `pre-commit install`. After changing dependencies run `uv lock` and commit the updated lockfile.

## Architecture

The pipeline has two stages: **ingest** (download) and **clean** (transform). They run independently or together via the parent `pipeline` flow.

```
AQMesh API ──► client.py ──► flows/ingest.py ──► data/raw/
                                                       │
                                                       ▼
                                          flows/clean.py ──► data/clean/
```

**Key design constraints:**
- Raw files are **append-only and never modified**. The clean step always rebuilds from scratch.
- State is tracked at two levels: the **AQMesh server-side cursor** (primary — the API's `/LocationData/Next` endpoint advances a per-(location, param) pointer on the server) and **`data/state/pointers.json`** (local audit trail only — not used to filter API requests).
- Interrupted runs are safe: the server cursor only advances on a successful API call, so the next run retries failed pairs automatically.

**Module responsibilities:**
- `config.py` — Pydantic settings with `AQMESH_` env prefix; `get_settings()` is called at runtime (not module-level) so tests can set env vars before construction.
- `client.py` — bearer-token auth with auto-refresh; `get_assets()` for pod listing; `iter_location_data()` generator for cursor-based batched fetches.
- `models.py` — `Param` enum (`gas`/`particle`), `Asset` dataclass, sentinel constants.
- `storage.py` — raw JSON batch I/O, CSV writes, atomic pointer updates (write-then-rename).
- `transform.py` — deduplication by reading number, sentinel → NaN, calibration (`prescaled × slope + offset`). `resample_5min` is scaffolded but not yet implemented.
- `flows/ingest.py` — Prefect flow; each (location, param) pair is a separate task with 3 retries.
- `flows/clean.py` — Prefect flow; reads all raw files per location, deduplicates, cleans, writes per-param CSVs.
- `flows/pipeline.py` — parent flow registered as `aqmesh-pipeline/hourly`; runs ingest then clean.
- `cli.py` — entry point for the `aqmesh` command.

## Data layout

```
data/
  raw/location=<n>/param={gas,particle}/<pulled_at>_<seq>.json
  clean/location=<n>/aqmesh_<n>_{gas,particle}.csv
  state/pointers.json
```

## Testing notes

Tests use Prefect's in-process ephemeral mode (configured in `conftest.py`) — no external Prefect server is needed. HTTP calls to the AQMesh API are mocked with `respx`. The `settings` fixture points at a `tmp_path` data root; use it rather than constructing `Settings` directly.

## Production

Deployed as two systemd services (`prefect-server`, `prefect-worker`) on an Ubuntu 24.04 VPS. The schedule is `6 * * * *` (Europe/London) — the :06 offset gives the API time to receive pod transmissions that occur on the hour. Deploy and update via:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

See `docs/` for deployment, service management, troubleshooting, and backfill instructions.
