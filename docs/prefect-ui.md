# Prefect web UI

Prefect 3 ships a built-in **web UI** (a management console / dashboard) served by the same
`prefect-server` process this deployment already runs — no extra component to install. It lets you
watch flow and task runs, read their logs, inspect schedules and deployments, browse work pools,
and trigger ad-hoc runs from a browser. For how the server itself is deployed, see
[`deployment.md`](deployment.md).

## What the UI shows

| Area | What you get |
| --- | --- |
| **Dashboard** | Overview of recent flow runs with a run-history timeline and filters (date range, state, flow name, deployment, tags). |
| **Flow Runs** | Every run of `aqmesh-pipeline` and its sub-flows (`ingest_raw`, `clean_data`) with state, duration, **logs**, task runs, and sub-flow runs. |
| **Deployments** | The `aqmesh-pipeline/hourly` deployment and its `6 * * * *` schedule (defined in [`prefect.yaml`](../prefect.yaml)). |
| **Work Pools** | The `process`-type `aqmesh-pool` and the worker polling it. |

From a deployment's page you can **trigger a run on demand** — the UI equivalent of the
`prefect deployment run aqmesh-pipeline/hourly` command in
[`deployment.md`](deployment.md#verify-the-deployment).

## Where it lives in this deployment

The UI is served at **`http://127.0.0.1:4200`** by the `prefect-server` systemd unit
([`deploy/systemd/prefect-server.service`](../deploy/systemd/prefect-server.service)). The server
binds to **localhost only** and is **not** exposed publicly (see
[`system-requirements.md`](system-requirements.md) — no inbound network access). On the VM itself,
open `http://127.0.0.1:4200` in a browser.

## Accessing it remotely (SSH tunnel)

Because the server listens on `127.0.0.1` only, reach the UI from your own machine by forwarding the
port over SSH — this needs **no change to the deployment** and keeps the server unexposed:

```bash
ssh -L 4200:127.0.0.1:4200 user@vm-host
# then open http://127.0.0.1:4200 in your local browser
```

While the tunnel is open, the local URL points at the Prefect UI on the VM.

## Optional: `PREFECT_UI_URL`

URLs that Prefect prints in logs or the CLI default to `http://127.0.0.1:4200`. If you want those
links to reflect how you actually reach the UI, set `PREFECT_UI_URL` accordingly. It is **not**
required for this setup. See the [settings reference](https://docs.prefect.io/v3/develop/settings-ref).

## Official documentation

| Topic | Link |
| --- | --- |
| Self-host the server via the CLI (starting the server + the UI at `127.0.0.1:4200`) | <https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli> |
| Prefect server overview | <https://docs.prefect.io/v3/manage/server/index> |
| Get started with Prefect 3 | <https://docs.prefect.io/v3/get-started> |
| Settings reference (`PREFECT_UI_URL` and others) | <https://docs.prefect.io/v3/develop/settings-ref> |
