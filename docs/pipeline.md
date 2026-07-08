# Pipeline: scheduling, state, and backfill

## How runs are triggered

The pipeline runs as a Prefect deployment (`aqmesh-pipeline/hourly`, defined in `prefect.yaml`).
A Prefect deployment is a server-side record that stores the schedule and entrypoint metadata
separately from the flow code, so the Prefect Scheduler can queue runs without touching the
codebase. See the [Prefect Deployments docs](https://docs.prefect.io/v3/concepts/deployments).

The schedule is `6 * * * *` (cron, Europe/London timezone) — every hour at :06 past.
The offset is deliberate: AQMesh pods transmit on the hour, so polling a few minutes later
gives the API time to have the latest readings available.

Each triggered run is an **independent, stateless invocation** of `pipeline()`. Prefect tracks
its own execution state (`Scheduled → Running → Completed / Failed`) but holds no memory of
which readings have already been fetched. That responsibility belongs to the AQMesh API cursor
and `state/pointers.json`.

## How the pipeline knows what data to fetch next

There are two complementary layers of state.

### Layer 1 — AQMesh server-side cursor (primary)

The AQMesh API exposes a `/LocationData/Next/{location}/{param}` endpoint. Each successful
call advances a **server-side pointer** for that (location, param) pair and returns the next
unseen batch of readings. The client loops until the server signals no more data (HTTP 204 or
an empty array):

```
# client.py — iter_location_data
while True:
    batch = api.get("/LocationData/Next/{location}/{param}/…")
    if not batch:
        break
    yield batch
```

This is the primary mechanism for "continue from where we left off." Because the cursor lives
on the AQMesh server, successive hourly runs automatically pick up from the newest undelivered
readings with no date arithmetic required on the client.

### Layer 2 — `state/pointers.json` (local audit + resilience)

After each successful fetch, `storage.py` records what was received:

```json
{
  "510": {
    "gas":      { "last_reading_number": 3256955, "last_datestamp": "2019-04-19T09:30:00", "new_readings": 2 },
    "particle": { "last_reading_number": 15622255, "last_datestamp": "2019-03-09T16:11:00", "new_readings": 1 }
  }
}
```

`pointers.json` is **not** used to filter API requests — the server cursor handles that.
Its roles are:

- **Audit trail** — a local record of when and how much data each run pulled, useful for
  diagnosing gaps or unexpected zero outputs.
- **Failure bookmarking** — if a fetch fails, its pointer entry is deliberately skipped
  (`ingest.py:106`). Because the API call that failed never succeeded, the server cursor for
  that pair also did not advance, so the next run will retry from the same point without loss.

Writes are atomic: the file is written to a temporary path then renamed, so an interrupted run
cannot corrupt the existing state.

Raw batch files (`raw/location=<n>/param=<gas|particle>/<pulled_at>_<seq>.json`) use the same
tmp → rename pattern, plus a `.sha256` integrity sidecar verified on read — see
[Raw file integrity in architecture.md](architecture.md#design-decisions) for detail.

## Automatic gap fill

If the pipeline is down for several hours, or a run fails partway through, the API cursor for
each affected (location, param) pair continues to accumulate undelivered batches on the server.
The next successful run drains all of them in a single loop. **No manual intervention or
backfill flag is needed** — this is a consequence of the cursor-per-pair design.

## Explicit date-range backfill

There is **no date-range backfill** in the current pipeline. The CLI (`cli.py`) accepts no
`--from-date` or `--to-date` arguments. If the server-side cursor has already advanced past a
window (i.e. the data was delivered to a previous run), it cannot be re-requested through the
normal flow.

The AQMesh API provides a **Repeat** endpoint (manual section 4.11) that re-delivers the most
recently sent batch for a given (location, param) pair *without* advancing the server-side
cursor. Use `aqmesh repeat` to re-ingest that batch:

```bash
aqmesh repeat --location 510 --param gas   # re-fetch last gas batch for location 510
aqmesh repeat --location 510               # both gas and particle
aqmesh repeat --all --yes                  # every location/param pair
aqmesh repeat --location 510 --dry-run     # preview without making any API calls
```

This writes a new raw file to the raw store; deduplication happens automatically on the next
`aqmesh clean` run. `state/pointers.json` is not modified — the server cursor has not changed.

To recover batches **older than the last one**, contact EI support to have the server-side
pointer reset manually (API manual section 3.3). Data over one year old requires special
permission to access.

## Triggering historical Prefect runs (Prefect-level backfill)

Prefect 3.x has no `prefect deployment backfill` command. Instead, two mechanisms let you
create flow runs for historical time windows.

> **Verify before relying on these.** The `/deployments/{id}/schedule` REST payload and the
> `prefect deployment run --start-at` flag are version-sensitive — confirm both against the
> Prefect version actually deployed (`prefect version`) before using them, rather than during
> an incident.

### Option A — REST API (recommended for date ranges)

`POST /deployments/{id}/schedule` accepts `start_time` and `end_time` as ISO 8601 strings.
Prefect will create `SCHEDULED` runs for every interval in that range based on the
deployment's cron schedule. The Prefect docs describe this as the intended backfill path:

```bash
curl -X POST "$PREFECT_API_URL/deployments/$(prefect deployment inspect aqmesh-pipeline/hourly --json | jq -r .id)/schedule" \
  -H "Content-Type: application/json" \
  -d '{
        "start_time": "2024-03-01T00:00:00Z",
        "end_time":   "2024-03-08T00:00:00Z"
      }'
```

This submits one `SCHEDULED` flow run per cron tick in the window. A work pool must be active
to pick them up.

### Option B — CLI / SDK loop (recommended for individual runs)

```bash
# single past run
prefect deployment run aqmesh-pipeline/hourly --start-at "2024-03-01 06:00"
```

```python
# Python — loop over historical hours
from prefect.deployments import run_deployment
from datetime import datetime, timedelta, timezone

start = datetime(2024, 3, 1, tzinfo=timezone.utc)
end   = datetime(2024, 3, 8, tzinfo=timezone.utc)
dt    = start
while dt < end:
    run_deployment(
        name="aqmesh-pipeline/hourly",
        scheduled_time=dt,
        idempotency_key=f"backfill-{dt.isoformat()}",  # prevents duplicates on retry
        timeout=0,   # don't block; fire-and-forget
    )
    dt += timedelta(hours=1)
```

### Important caveat for this pipeline

Triggering historical Prefect runs only re-executes the flow code — it does **not** rewind
the AQMesh server-side cursor. Because the cursor determines what data the API returns, a
re-run will fetch whatever data is *currently* next in the queue, not data from the target
date. A Prefect-level backfill is therefore only meaningful if the AQMesh cursor has been
reset separately (a manual API operation) to align with the intended historical window.

## Failure recovery

Each per-(location, param) fetch is a Prefect task with retries:

```python
# ingest.py:23
@task(retries=3, retry_delay_seconds=30, cache_policy=NO_CACHE)
def ingest_location_param(...):
```

Per the [Prefect States docs](https://docs.prefect.io/v3/concepts/states), a failed task enters
`AwaitingRetry` (a `SCHEDULED` type state) and then `Retrying` (`RUNNING`) up to three times.
If all retries are exhausted the task fails, but the parent flow continues — other
(location, param) pairs are unaffected. The pointer for the failed pair is not written,
preserving the last-known-good position for the next hourly run.

A non-404 fetch failure is reported one of two ways, distinguished by the `Assets_V1`
lifetime reading counters on the pod's [`Asset`](../src/aqmesh_pipeline/models.py) (issue #64):

- **`"failed"`** (`ERROR`) — a genuine unexpected error on a pod that otherwise reports this
  param fine (both `last_gas_reading_number` and `last_particle_reading_number` are
  plausible). Worth investigating.
- **`"unsupported"`** (`WARNING`, rolled up at `INFO`) — the pod has never recorded a reading
  for this param at all while the other param has a real counter, indicating a gas-only or
  particle-only pod hardware variant (manual 4.18) rather than a fault. Expected and
  permanent; no pointer is written, same as `"failed"`.

## Summary

| Concern | Mechanism |
| --- | --- |
| When to run | Prefect cron schedule `6 * * * *`, deployment `aqmesh-pipeline/hourly` |
| What to fetch next | AQMesh server-side cursor per (location, param) via `/LocationData/Next` |
| Local progress record | `state/pointers.json` — audit trail and failure bookmark |
| Automatic gap fill | Yes — server cursor accumulates missed batches; next run drains them |
| Re-fetch last batch | `aqmesh repeat` — calls `/LocationData/Repeat`; does not advance cursor |
| Explicit date backfill | No date-range flag; `aqmesh repeat` re-fetches the last batch, older data needs an EI admin cursor reset; Prefect-level historical runs are possible via REST / `run_deployment()` but only after that reset |
| Partial-failure recovery | Prefect task retries (×3); failed pairs skip pointer write; retried next run |
| Hardware-mismatch pods | Gas-only/particle-only pods (manual 4.18) log `WARNING`/`status: "unsupported"`, not `ERROR`/`"failed"` |
