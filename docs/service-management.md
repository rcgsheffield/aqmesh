# Service management

Day-to-day operator reference for the running AQMesh pipeline. For first-time installation or
rolling out code updates, see [`deployment.md`](deployment.md). For sizing the VM, see
[`system-requirements.md`](system-requirements.md).

## Service control

Two systemd units make up the deployment:

| Unit | Role |
| --- | --- |
| `prefect-server` | Prefect API server + UI, listening on `127.0.0.1:4200` |
| `prefect-worker` | Prefect worker, polling the `aqmesh-pool` work pool |

### Status

```bash
sudo systemctl status prefect-server prefect-worker
```

### Start, stop, restart

```bash
# Both services together (most common)
sudo systemctl restart prefect-server prefect-worker

# Individually
sudo systemctl restart prefect-server
sudo systemctl restart prefect-worker
```

**When to restart each:**

- **Worker only** — after editing `/opt/aqmesh/.env` (credential rotation, data path change). The
  worker reads the environment file on start; the server does not need to restart.
- **Server only** — after changing server-side config (e.g. environment variables in
  `prefect-server.service`). The worker reconnects automatically once the server is back up.
- **Both** — after a code update (`bootstrap.sh` handles this automatically; only do it manually
  if you need to force a restart without re-running the full provisioning script).

## Viewing logs

### Live tail

```bash
sudo journalctl -fu prefect-server
sudo journalctl -fu prefect-worker
```

### Last N lines

```bash
sudo journalctl -u prefect-server --lines 200
sudo journalctl -u prefect-worker --lines 200
```

### Date range

```bash
sudo journalctl -u prefect-server --since "2025-01-15 08:00" --until "2025-01-15 10:00"
```

### Export to file

```bash
sudo journalctl -u prefect-server --since "-24h" --output cat > /tmp/prefect-server.log
```

### Flow-run logs

Prefect stores structured flow and task run logs in its SQLite database
(`/opt/aqmesh/.prefect/prefect.db`). To read them from the CLI:

```bash
# List recent runs first to get a run ID
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect flow-run ls --limit 20'

# Then fetch logs for a specific run
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect flow-run logs <run-id>'
```

Or browse them in the Prefect web UI — see [Accessing the web UI remotely](#accessing-the-web-ui-remotely-ssh-tunnel).

## Health checks

### Prefect API

```bash
curl -s http://127.0.0.1:4200/api/health | python3 -m json.tool
```

A healthy response looks like `{"status": "healthy"}`. If `curl` hangs or returns an error, the
`prefect-server` unit is down — check `sudo systemctl status prefect-server`.

### Worker polling

Confirm the worker is connected and polling its work pool:

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect work-pool inspect aqmesh-pool'
```

Check that `last_polled_at` is recent (within the last minute or two). Alternatively, tail the
worker logs and look for poll activity:

```bash
sudo journalctl -fu prefect-worker | grep -i poll
```

## Accessing the web UI remotely (SSH tunnel)

Prefect 3 ships a built-in web UI served by `prefect-server` at `http://127.0.0.1:4200`. It lets
you watch flow and task runs, read their logs, inspect schedules and deployments, browse work
pools, and trigger ad-hoc runs from a browser.

Because the server binds to `127.0.0.1` only and is not exposed publicly, forward the port over
SSH to reach the UI from your own machine:

```bash
ssh -L 4200:127.0.0.1:4200 user@vm-host
# then open http://127.0.0.1:4200 in your local browser
```

No change to the deployment is needed; the server stays unexposed.

### What the UI shows

| Area | What you get |
| --- | --- |
| **Dashboard** | Overview of recent flow runs with a run-history timeline and filters (date range, state, flow name, deployment, tags). |
| **Flow Runs** | Every run of `aqmesh-pipeline` and its sub-flows (`ingest_raw`, `clean_data`) with state, duration, logs, task runs, and sub-flow runs. |
| **Deployments** | The `aqmesh-pipeline/hourly` deployment and its `6 * * * *` schedule (defined in [`prefect.yaml`](../prefect.yaml)). |
| **Work Pools** | The `process`-type `aqmesh-pool` and the worker polling it. |

From a deployment's page you can trigger a run on demand — the UI equivalent of the
`prefect deployment run aqmesh-pipeline/hourly` CLI command.

### Optional: `PREFECT_UI_URL`

URLs that Prefect prints in logs or the CLI default to `http://127.0.0.1:4200`. If you want those
links to reflect how you actually reach the UI (e.g. via a tunnel or reverse proxy), set
`PREFECT_UI_URL` accordingly. It is not required for this setup. See the
[settings reference](https://docs.prefect.io/v3/develop/settings-ref).

## Scheduled run management

All CLI commands below must run as the `aqmesh` service user with the API URL set. The wrapper
pattern is:

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect <subcommand>'
```

### Pause the hourly schedule

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api \
   uv run prefect deployment pause aqmesh-pipeline/hourly'
```

### Resume the hourly schedule

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api \
   uv run prefect deployment resume aqmesh-pipeline/hourly'
```

### Trigger a manual run

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api \
   uv run prefect deployment run aqmesh-pipeline/hourly'
```

You can also do this from the Prefect UI — navigate to **Deployments → aqmesh-pipeline/hourly**
and click **Run**.

### List recent runs

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api \
   uv run prefect flow-run ls --limit 20'
```

### Cancel an in-flight run

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api \
   uv run prefect flow-run cancel <run-id>'
```

## Credential rotation

To update the AQMesh API username or password without a full re-provisioning run:

1. Edit `/opt/aqmesh/.env` as root (or `sudo`):

   ```bash
   sudo nano /opt/aqmesh/.env
   ```

   Update `AQMESH_USERNAME` and/or `AQMESH_PASSWORD`.

2. Restart the worker (it reads `.env` on start; the server does not need to restart):

   ```bash
   sudo systemctl restart prefect-worker
   ```

3. Verify the next scheduled run completes, or trigger one manually (see above).

## Common failure scenarios

### Worker exits unexpectedly

```bash
sudo journalctl -u prefect-worker -n 100
```

Common causes: invalid API credentials (401 responses), Prefect API unreachable, or the data
volume unmounted. Fix the underlying issue and then `sudo systemctl restart prefect-worker`.

### Prefect server fails to start

```bash
sudo journalctl -u prefect-server -n 100
```

Common causes: port 4200 already in use, or a corrupt SQLite database at
`/opt/aqmesh/.prefect/prefect.db`. For `database is locked` errors that appear in the server logs
but are not actually breaking runs, see [`troubleshooting.md`](troubleshooting.md).

### Data volume full or unmounted

```bash
df -h /mnt/aqmesh-data
mount | grep aqmesh
```

If the volume is unmounted, remount it and restart the worker so it can write output files again:

```bash
sudo mount /mnt/aqmesh-data
sudo systemctl restart prefect-worker
```

If the volume is full, archive or remove old data files under `/mnt/aqmesh-data/raw/` before
restarting. For expected data growth rates, see [`system-requirements.md`](system-requirements.md).

### API credentials expired

The worker logs will show HTTP 401 responses from `api.aqmeshdata.net`. Follow the
[Credential rotation](#credential-rotation) steps above.

## Further reading

| Topic | Link |
| --- | --- |
| Self-host the Prefect server via CLI | <https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli> |
| Prefect server overview | <https://docs.prefect.io/v3/manage/server/index> |
| Get started with Prefect 3 | <https://docs.prefect.io/v3/get-started> |
| Settings reference (`PREFECT_UI_URL` and others) | <https://docs.prefect.io/v3/develop/settings-ref> |
