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
uv run aqmesh pipeline         # metadata + ingest + clean
uv run aqmesh metadata         # sync location/sensor metadata; write info.json per pod
uv run aqmesh ingest           # download raw data only
uv run aqmesh clean            # rebuild CSVs from raw store
uv run aqmesh check            # health check: auth, pods, server freshness + notices
uv run aqmesh ping             # server health/freshness probe (no credentials needed)
uv run aqmesh sensors          # fleet sensor age/expiry/failures (read-only)
```

Environment is configured via `.env` (copy from `.env.example`). Set `AQMESH_ENVIRONMENT=prod` to target the production API; default is `test` (`apitest.aqmeshdata.net`).

Pre-commit hooks keep `uv.lock` in sync — install once with `pre-commit install`. After changing dependencies run `uv lock` and commit the updated lockfile.

## Architecture

Three-stage pipeline: **metadata** (fetch location/sensor registry from the API → `data/state/assets.json` + `data/clean/location=<n>/info.json`), **ingest** (download raw readings → `data/raw/`), and **clean** (transform → `data/clean/`). All three run together via the parent `pipeline` flow. Each (location, param) pair in ingest/clean is a separate Prefect task.

The repo is a uv workspace with two independently versioned packages: **`aqmesh-client`** (`packages/aqmesh-client/`, importable as `aqmesh_client` — a dependency-light AQMesh REST client: `client.py`, `models.py`, and `APISettings` in `config.py`; depends only on `httpx`/`pydantic`; published to PyPI standalone as `aqmesh`) and **`aqmesh-pipeline`** (repo root, importable as `aqmesh_pipeline` — everything else, which depends on `aqmesh-client`). The pipeline's `Settings` subclasses the client's `APISettings` to add the data-layout paths. Import the client from `aqmesh_client`, never from `aqmesh_pipeline`.

Non-obvious invariants:
- Raw files are **append-only and never modified**. The clean step always rebuilds from scratch.
- The **AQMesh server-side cursor** is the primary state — the `/LocationData/Next` endpoint advances a per-(location, param) pointer on the server. `data/state/pointers.json` is a local audit trail only, not used to filter requests.
- Interrupted runs are safe: the server cursor only advances on a successful API call, so the next run retries failed pairs automatically.

Module map, data layout, and infrastructure detail: **docs/architecture.md**. Scheduling, state, and backfill: **docs/pipeline.md**. AQMesh REST API endpoints (paths, params, response shapes, distilled from the vendor PDF): **docs/api-reference/**.

## Testing notes

Tests use Prefect's in-process ephemeral mode (configured in `conftest.py`) — no external Prefect server is needed. HTTP calls to the AQMesh API are mocked with `respx`. The `settings` fixture points at a `tmp_path` data root; use it rather than constructing `Settings` directly.

The ephemeral server occasionally returns a transient `503 Service Unavailable` under CI resource contention (unrelated to the code under test). `pytest-rerunfailures` auto-retries only failures matching that specific error (`--only-rerun` in `pyproject.toml`) — any other test failure still fails outright.

### CI checks (run automatically on every PR)

- **lock-check** — `uv lock --check` (lockfile in sync)
- **lint** — `ruff check` + `ruff format --check`
- **security** — `pip-audit` (dependency CVEs) + `bandit` (static analysis)
- **test** — `pytest` on Python 3.12 and 3.13 (coverage ≥ 90% enforced)
- **actionlint** — GitHub Actions workflow syntax
- **shellcheck** — shell script linting
- **link-check** — broken links in Markdown docs

PR test plans should only list manual or environment-specific steps not covered above.

## Production

Deployed as two systemd services (`prefect-server`, `prefect-worker`) on Ubuntu 24.04, scheduled `6 * * * *` (Europe/London). Deploy/update:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh bash deploy/bootstrap.sh
```

See **docs/** for deployment, service management, troubleshooting, and backfill.
