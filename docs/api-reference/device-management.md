# Device management (write operations)

Manual §§ 4.4, 4.5, 4.6, 4.7, 4.9, 4.18. These **mutate hardware configuration or
state**. The pipeline is a read-only data consumer and **does not call any of
them** — they are documented here for completeness and so nobody wires them into
an automated flow by accident.

> ⚠️ **Out of scope for this repo.** Fleet configuration (sampling frequencies,
> rebasing, sensor replacement) is done through the AQMesh web portal by the
> people who own the hardware. Automating these from the pipeline risks
> disrupting live monitoring. If you ever genuinely need one, add it behind an
> explicit, confirmed CLI action — never inside `ingest`/`clean`.

## Sampling frequencies

| Endpoint | Method + path | Applies to |
| --- | --- | --- |
| Gas frequencies (4.4) | `PATCH /api/Pods/GasFrequencies` | v3.xx firmware pods |
| PM frequencies (4.5) | `PATCH /api/Pods/PMFrequencies` | v3.xx firmware pods |
| Pod frequencies (4.18) | `PATCH /api/Pods/PodFrequencies` | v5.1+ firmware (combined Gas+PM) |

`PodFrequencies` body (v5.x): `Serial_Number`, `Particle_P1` (pump run time 30/60s),
`Gas_P1` (sample frequency 5/10/30s), `Pod_P2` (reading interval), `Pod_P3`
(transmission frequency). Values must satisfy divisibility/range rules or the
call returns `400`. Defaults differ for battery vs DC/solar power.

## State operations

| Endpoint | Method + path | Effect |
| --- | --- | --- |
| Restabilise (4.6) | `POST /api/Pods/Restabilise/{Serial_Number}` | Re-stabilise all sensors in a pod |
| Rebase pod (4.7.1) | `POST /api/Pods/ReBase/{Serial_Number}` | Re-base all sensors in a pod |
| Rebase sensor (4.7.2) | `POST /api/Pods/ReBase/` (body: pod + sensor serial + `event_time`) | Re-base one sensor |
| Confirm sensor replacement (4.9) | `POST /api/Pods/UpdateReplaceSensor/{Serial}/{SensorType}` | Record a replacement and re-stabilise |

Success is `204 No Content`; typical errors are `400`, `401`, `404`. Sensors that
enter stabilisation automatically rebase afterwards, which produces the
[obscured-value sentinels](readings.md#data-conditions--obscured-values-412) you
see in readings during that window.

---

Next: [diagnostics](diagnostics.md) · [readings](readings.md) · [index](README.md)
