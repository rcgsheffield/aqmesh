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

Two-stage pipeline: **ingest** (download from the AQMesh API → `data/raw/`) and **clean** (transform → `data/clean/`), run independently or together via the parent `pipeline` flow. Each (location, param) pair is a separate Prefect task.

Non-obvious invariants:
- Raw files are **append-only and never modified**. The clean step always rebuilds from scratch.
- The **AQMesh server-side cursor** is the primary state — the `/LocationData/Next` endpoint advances a per-(location, param) pointer on the server. `data/state/pointers.json` is a local audit trail only, not used to filter requests.
- Interrupted runs are safe: the server cursor only advances on a successful API call, so the next run retries failed pairs automatically.

Module map, data layout, and infrastructure detail: **docs/architecture.md**. Scheduling, state, and backfill: **docs/pipeline.md**.

## Testing notes

Tests use Prefect's in-process ephemeral mode (configured in `conftest.py`) — no external Prefect server is needed. HTTP calls to the AQMesh API are mocked with `respx`. The `settings` fixture points at a `tmp_path` data root; use it rather than constructing `Settings` directly.

## Production

Deployed as two systemd services (`prefect-server`, `prefect-worker`) on Ubuntu 24.04, scheduled `6 * * * *` (Europe/London). Deploy/update:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

See **docs/** for deployment, service management, troubleshooting, and backfill.
