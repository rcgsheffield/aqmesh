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
# client.py:127-149
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

## Automatic gap fill

If the pipeline is down for several hours, or a run fails partway through, the API cursor for
each affected (location, param) pair continues to accumulate undelivered batches on the server.
The next successful run drains all of them in a single loop. **No manual intervention or
backfill flag is needed** — this is a consequence of the cursor-per-pair design.

## Explicit date-range backfill

There is **no date-range backfill** in the current pipeline. The CLI (`cli.py`) accepts no
`--from-date` or `--to-date` arguments. If the server-side cursor has already advanced past a
window (i.e. the data was delivered to a previous run), it cannot be re-requested through the
<<<<<<< feat/repeat-last
normal flow.

The AQMesh API provides a **Repeat** endpoint (manual section 4.11) that re-delivers the most
recently sent batch for a given (location, param) pair *without* advancing the server-side
cursor. Use `aqmesh repeat-last` to re-ingest that batch:

```bash
aqmesh repeat-last --location 510 --param gas   # re-fetch last gas batch for location 510
aqmesh repeat-last --location 510               # both gas and particle
aqmesh repeat-last --all --yes                  # every location/param pair
aqmesh repeat-last --location 510 --dry-run     # preview without making any API calls
```

This writes a new raw file to the raw store; deduplication happens automatically on the next
`aqmesh clean` run. `state/pointers.json` is not modified — the server cursor has not changed.

To recover batches **older than the last one**, contact EI support to have the server-side
pointer reset manually (API manual section 3.3). Data over one year old requires special
permission to access.
=======
normal flow. Recovery would require resetting the AQMesh server-side cursor, which is a manual
API operation outside this codebase.
>>>>>>> main

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

## Summary

| Concern | Mechanism |
| --- | --- |
| When to run | Prefect cron schedule `6 * * * *`, deployment `aqmesh-pipeline/hourly` |
| What to fetch next | AQMesh server-side cursor per (location, param) via `/LocationData/Next` |
| Local progress record | `state/pointers.json` — audit trail and failure bookmark |
| Automatic gap fill | Yes — server cursor accumulates missed batches; next run drains them |
<<<<<<< feat/repeat-last
| Re-fetch last batch | `aqmesh repeat-last` — calls `/LocationData/Repeat`; does not advance cursor |
| Explicit date backfill | No — use `aqmesh repeat-last` for the last batch; older data requires EI admin reset |
=======
| Explicit date backfill | No — not implemented; requires manual server-side cursor reset |
>>>>>>> main
| Partial-failure recovery | Prefect task retries (×3); failed pairs skip pointer write; retried next run |
