# Deployment

How to roll out the AQMesh pipeline to an **Ubuntu 24.04** VM using the scripts in
[`deploy/`](../deploy).

## Overview

The pipeline runs as a self-hosted [Prefect 3](https://docs.prefect.io/v3/get-started) server and
worker on a single VM, both managed by systemd. The worker polls a `process`-type work pool named
`aqmesh-pool` and executes the `aqmesh-pipeline` flow on an hourly schedule (defined in
[`prefect.yaml`](../prefect.yaml)). The Prefect server binds to `127.0.0.1:4200` only — it is **not**
exposed publicly. The full provisioning is done by one idempotent script, `deploy/bootstrap.sh`.

For background on running Prefect from the CLI, see the upstream guide:
<https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli>.

## Prerequisites

- An **Ubuntu 24.04** VM with `root` / `sudo` access. See [`system-requirements.md`](system-requirements.md) for sizing (CPU / RAM / disk).
- Outbound HTTPS access to:
  - `astral.sh` — to install [uv](https://docs.astral.sh/uv/) (the dependency manager).
  - `api.aqmeshdata.net` — the AQMesh production API.
- The **shared storage volume** mounted on the VM (default mount point `/mnt/aqmesh-data`). Cleaned
  CSVs and the append-only raw store are written here.
- **AQMesh API credentials** (username and password).
- A **checkout of this repository** on the VM (e.g. `git clone` into your home directory). You run
  `bootstrap.sh` from that checkout.

> Python 3.12+ is required, but you do not need to install it yourself — `uv` provisions the correct
> interpreter automatically during `uv sync`.

## What `deploy/` contains

| File | Purpose |
| --- | --- |
| `deploy/bootstrap.sh` | Idempotent provisioning script; does everything below. |
| `deploy/systemd/prefect-server.service` | systemd unit for the Prefect server (`127.0.0.1:4200`). |
| `deploy/systemd/prefect-worker.service` | systemd unit for the worker polling `aqmesh-pool`. |
| `prefect.yaml` (repo root) | Deployment definition: flow entrypoint, work pool, and hourly schedule. |

## Run the bootstrap

From the repository checkout on the VM:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

The three environment variables are optional overrides (shown with their defaults):

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_DIR` | `/opt/aqmesh` | Where the application code is installed. |
| `DATA_ROOT` | `/mnt/aqmesh-data` | The mounted shared storage volume for raw/clean data. |
| `SERVICE_USER` | `aqmesh` | The system user the services run as. |

The script is **idempotent** — safe to re-run, which is exactly how you roll out updates (see
[Rolling out updates](#rolling-out-updates)). It:

1. Creates the `aqmesh` system service user (no login shell) if it does not already exist.
2. Copies the repo into `APP_DIR` with `rsync` (excluding `.git`, `.venv`, `data/`, `.prefect/`).
3. Ensures `DATA_ROOT` exists and is owned by the service user.
4. Installs `uv` for the service user (if missing).
5. Installs production dependencies with `uv sync --no-dev`.
6. Creates `APP_DIR/.env` from `.env.example` (only if absent), setting `AQMESH_DATA_ROOT` to
   `DATA_ROOT` and `AQMESH_ENVIRONMENT=prod`, then `chmod 600`. **Credentials are placeholders at
   this point** — see the next section.
7. Installs and enables the two systemd units, then **restarts** `prefect-server` (a re-run
   reloads it so any new dependencies and Prefect database migrations take effect).
8. Waits (up to ~60s) for the Prefect API health check at `http://127.0.0.1:4200/api/health`.
9. Creates the `aqmesh-pool` work pool and deploys the flow with `prefect deploy --all`.
10. **Restarts** `prefect-worker` so it picks up the new flow code and dependencies (the worker
    holds imported code in memory, so a plain "start" would keep running the old version).

The two services are **restarted** rather than just started, so re-running the script after a
`git pull` actually rolls out the new code. The `.env` is excluded from the file copy, so your
credentials survive every re-run.

## Set credentials

Bootstrap writes a `.env` with placeholder credentials. Edit it with the real AQMesh username and
password, then restart the worker so it picks them up:

```bash
sudo nano /opt/aqmesh/.env          # set AQMESH_USERNAME and AQMESH_PASSWORD
sudo systemctl restart prefect-worker
```

Key variables in `.env` (see [`.env.example`](../.env.example) for the complete list and defaults):

| Variable | Notes |
| --- | --- |
| `AQMESH_USERNAME` | AQMesh API username. |
| `AQMESH_PASSWORD` | AQMesh API password. |
| `AQMESH_DATA_ROOT` | Data volume path; set by bootstrap to `DATA_ROOT`. |
| `AQMESH_ENVIRONMENT` | `test` (apitest.aqmeshdata.net) or `prod` (api.aqmeshdata.net); set to `prod` by bootstrap. |

## Verify the deployment

1. **Both services are running:**

   ```bash
   systemctl status prefect-server prefect-worker
   ```

   Each should report `active (running)`.

2. **The server API is healthy:**

   ```bash
   curl -fsS http://127.0.0.1:4200/api/health
   ```

3. **The deployment and schedule are registered** (expect `aqmesh-pipeline/hourly`):

   ```bash
   sudo -u aqmesh bash -lc \
     'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect deployment ls'
   ```

4. **Follow the logs:**

   ```bash
   journalctl -u prefect-worker -f      # worker / flow-run logs
   journalctl -u prefect-server -f      # server logs
   ```

5. **Trigger a run immediately** (instead of waiting for the next scheduled run) to confirm the
   pipeline works end-to-end:

   ```bash
   sudo -u aqmesh bash -lc \
     'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect deployment run aqmesh-pipeline/hourly'
   ```

   Watch the worker logs, then confirm files appear under the data volume:

   ```bash
   ls /mnt/aqmesh-data/raw/      # append-only raw JSON batches
   ls /mnt/aqmesh-data/clean/    # cleaned per-location CSVs
   ```

## Schedule

The flow runs at `6 * * * *` — six minutes past every hour, `Europe/London` (pods transmit on the
hour; the pipeline polls a few minutes after). To change the schedule, edit `prefect.yaml` and
re-run `bootstrap.sh` (or, as the service user, `uv run prefect deploy --all`).

## Rolling out updates

Updates use the **same script** as the first install. From the repository checkout on the VM:

```bash
cd ~/aqmesh                                   # your checkout of this repo
git pull
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

Because `bootstrap.sh` is idempotent, a re-run only applies the differences:

- **Code** is re-synced into `APP_DIR` (stale files removed via `rsync --delete`).
- **Dependencies** are reconciled by `uv sync --no-dev` against the checked-in `uv.lock`.
- **The deployment and schedule** are re-applied by `prefect deploy --all`, so changes to
  `prefect.yaml` (entrypoint, cron, description) take effect.
- **Both services are restarted**, so the running worker drops its old in-memory code and loads
  the new version.

What is **preserved** across an update:

| Preserved | Why |
| --- | --- |
| `/opt/aqmesh/.env` (credentials) | Excluded from the `rsync` copy. |
| `/mnt/aqmesh-data/` (raw + clean data) | On a separate volume; never touched by bootstrap. |
| Prefect server database (run history, work pool) | Lives under `PREFECT_HOME`; only migrated, never reset. |

### In-flight runs

Restarting the worker **interrupts any flow run in progress**. This is safe: the hourly schedule
fires again at the next hour, ingest is append-only and resumes from the stored pointers (no data
loss or duplication), and clean simply rebuilds the CSVs. Still, prefer to **deploy a few minutes
away from `:06`** so you are not racing a scheduled run.

After updating, re-run the checks in [Verify the deployment](#verify-the-deployment) — in
particular trigger a manual run and watch the logs:

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect deployment run aqmesh-pipeline/hourly'
journalctl -u prefect-worker -f
```

### Rolling back

The deployed code is whatever you have checked out. To revert to a previous release, check out the
prior commit (or tag) and re-run the same script:

```bash
cd ~/aqmesh
git checkout <previous-tag-or-commit>
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

`uv sync` will roll the dependencies back to that revision's `uv.lock` as well.

### Upgrading Prefect itself

Prefect is pinned in `pyproject.toml`/`uv.lock` and in `prefect-version` in
[`prefect.yaml`](../prefect.yaml). To upgrade it:

1. Bump the pin and refresh the lock (`uv lock`) — review the [Prefect release notes](https://docs.prefect.io/v3/resources/upgrade-to-prefect-3) for breaking changes first.
2. Commit, `git pull` on the VM, and re-run `bootstrap.sh`.

A self-hosted server **runs its database migrations automatically on startup**, so restarting
`prefect-server` (which the script does) applies them — no manual `prefect server database upgrade`
step is needed for the default SQLite backend. Because the server, worker, and flow all run from
the **same `APP_DIR` virtualenv**, the client and server are always the same Prefect version, which
avoids the version-skew errors described in the
[Prefect server concepts guide](https://docs.prefect.io/v3/concepts/server).

## Scaling note

The Prefect server uses its default SQLite backend, which is sufficient for this single-worker
`process` pool. Multi-worker setups require PostgreSQL (and Redis) — out of scope here; see the
[Prefect self-hosted guide](https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli) if you
need to scale beyond one worker.

Hitting errors? See [`troubleshooting.md`](troubleshooting.md).
