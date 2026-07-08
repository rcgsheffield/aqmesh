# Diagnostics & context (read-only)

Read-only endpoints that answer "is the server healthy, is the data fresh, and is
the hardware OK?" — useful context around a pipeline run. Implemented in
[`client.py`](../../packages/aqmesh-client/src/aqmesh_client/client.py) and surfaced by the
[`ping`](../../src/aqmesh_pipeline/cli.py), `check`, and `sensors` CLI commands.

## Server ping (4.16)

```
GET /serverping        # no authentication required
```

```json
{
  "server_time": "2018-07-10T09:02:42.417",
  "last_sequence_number": 106649,
  "most_recent_reading": "2018-07-10T08:57:00",
  "last_communication": "2018-07-10T09:00:47.193",
  "most_recent_processed": "2018-07-10T09:01:23.746",
  "version": "Vn 0.9"
}
```

A liveness + **freshness** probe: `most_recent_reading` tells you how stale the
upstream data is before trusting a run. Because it needs no token, it answers
"is the server up?" independently of whether our account can authenticate — so
[`aqmesh ping`](../../src/aqmesh_pipeline/cli.py) works even with missing/expired
credentials. Modelled by `ServerPing`.

## System notifications (4.17)

```
GET /notification/system
```

```json
[ { "system_information": "New API request available ..." } ]
```

Free-text operator notices, e.g. **planned downtime**. The client returns the
non-empty `system_information` strings (`get_system_notifications`). Folded into
`aqmesh check` so notices surface during the routine smoke test.

## Failed sensors (4.8)

```
GET /Pods/SensorFail
```

```json
[ {
  "sensor_serial_number": 11, "pod_serial_number": 704150,
  "sensor_type": "SO2", "fail_type": "Fail criteria exceeded",
  "fail_date": "2018-02-26T09:00:00", "status": "Sensor Allocated"
} ]
```

Sensors that have tripped their fail criteria. Modelled by `FailedSensor`; shown
by [`aqmesh sensors`](../../src/aqmesh_pipeline/cli.py).

## Sensor details (4.20)

```
GET /sensor/SensorDetail/{Active}
```

`Active`: `0` = all deployed pods, `1` = active/installed only.

> The manual (§4.20) documents a literal double slash before `{Active}`
> (`SensorDetail//{Active}`). In production that 404s — a single slash gets past
> routing and returns `401` instead (ownership-scoped, per the [data ownership
> checks](authentication.md#data-ownership-checks-42) below), so the manual's
> format appears to be wrong. See issue #121: this account still can't retrieve
> sensor details (401), which needs following up with AQMesh support as a
> permissions/entitlement question rather than a URL question.

Returns per-sensor status and lifetime. The fields the `SensorDetail` model
pins — `serial_number` (pod), `sensor_serial_number`, `sensor_type_name`,
`sensor_status_name`, `pod_status_name`, `age_in_months`, `expiry_date`,
`replacement_needed`. A non-null `replacement_needed` is a human-readable
recommendation, so [`aqmesh sensors`](../../src/aqmesh_pipeline/cli.py) flags
those rows. Useful for **data-quality triage**: an expired or failing sensor
explains anomalous readings.

> These three (`SensorFail`, `SensorDetail`, `notification/system`) are
> [ownership-scoped](authentication.md#data-ownership-checks-42) and so require a
> token; only `/serverping` is public.

---

Next: [authentication](authentication.md) · [readings](readings.md) · [assets](assets.md) · [device management](device-management.md)
