# Authentication & data ownership

Manual §§ 4.1, 4.2. Implemented in
[`AQMeshClient.authenticate`](../../src/aqmesh_client/client.py).

## Authenticate (4.1)

```
POST /Authenticate
Content-Type: application/json

{ "username": "...", "password": "..." }
```

**Response** `200 OK`:

```json
{ "token": "<bearer token>" }
```

- The token is valid for **120 minutes** (manual § 3.1). The client caches it and
  refreshes ~5 minutes early (`TOKEN_LIFETIME_SECONDS`, `TOKEN_REFRESH_BUFFER_SECONDS`).
- Every authenticated request sends `Authorization: Bearer <token>`. On a `401`,
  the client forces one re-authentication and retries once.
- A non-`200` response, or a `200` without a `token`, raises `AQMeshAuthError`.

Credentials come from `AQMESH_USERNAME` / `AQMESH_PASSWORD` (see
[`config.py`](../../src/aqmesh_pipeline/config.py) and `.env.example`).

## Data ownership checks (4.2)

The bearer token also identifies the requesting user, and every request is scoped
to their organisation:

- **List requests** return only items belonging to the user's organisation
  (e.g. only your pods appear in [`Assets_V1`](assets.md)).
- Requesting or modifying data the user cannot access returns `401 Unauthorized`.
- **Data service providers** see all PODs/owners/readings marked as using that
  provider, across customers; unmarked PODs return `401`.

This is why the [diagnostics](diagnostics.md) endpoints need authentication
(`SensorFail`, `SensorDetail`, `notification/system`) — their results are
ownership-scoped — while [`/serverping`](diagnostics.md#server-ping-416) does not.

---

Next: [readings](readings.md) · [assets](assets.md) · [diagnostics](diagnostics.md)
