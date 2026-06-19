# Troubleshooting

Operational issues seen on the deployed AQMesh pipeline and how to deal with them. For installing
and updating the deployment, see [`deployment.md`](deployment.md).

## `sqlite3.OperationalError: database is locked`

SQLite is single-writer. Prefect already enables the usual mitigations (WAL journaling,
`synchronous=NORMAL`, a 60 s `busy_timeout`), but the server runs several background service loops
(scheduler, foreman, late-runs, …) that write to the same DB file as ongoing flow/task state
updates. When two writers collide, SQLite can return `database is locked` *immediately* — the
`busy_timeout` does not cover that case. These errors come from background services (e.g.
`mark_deployments_ready`, part of the **Foreman** service) and are normally **non-fatal**: the
service retries on its next loop, so flow runs still complete.

**Confirm it is actually breaking runs first** — check that recent runs completed:

```bash
sudo -u aqmesh bash -lc \
  'cd /opt/aqmesh && PREFECT_API_URL=http://127.0.0.1:4200/api uv run prefect flow-run ls --limit 20'
```

If recent `aqmesh-pipeline` runs are `Completed`, the errors are log noise. You can gauge how often
they occur with:

```bash
journalctl -u prefect-server --since '-24h' | grep -c 'database is locked'
```

### Mitigations already applied

The [`prefect-server.service`](../deploy/systemd/prefect-server.service) unit sets two config-only
levers (issue [#16](https://github.com/rcgsheffield/aqmesh/issues/16)):

- **Less background write traffic** — the event persister and usage telemetry are disabled
  (`PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED=false`,
  `PREFECT_SERVER_ANALYTICS_ENABLED=false`). This deployment uses no automations or event feed.
- **Desynchronised service loops** — the periodic loops use mutually coprime (prime) intervals
  (`*_LOOP_SECONDS` = 61/17/23/7/11) so they almost never fire on the same tick.

These ship on the next `bootstrap.sh` run, which reinstalls the unit and restarts the server.

### If it persists

If lock errors persist *and* are actually breaking runs, the durable fix is to move the backend off
SQLite to **PostgreSQL** (set `PREFECT_SERVER_DATABASE_CONNECTION_URL` to a `postgresql+asyncpg://`
DSN — the `asyncpg` driver is already installed); see the
[Prefect self-hosted guide](https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli).
