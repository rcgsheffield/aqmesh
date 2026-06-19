# systemd unit files

This directory contains the shipped systemd unit files for the AQMesh pipeline:

| File | Unit |
| --- | --- |
| `prefect-server.service` | Prefect server bound to `127.0.0.1:4200` |
| `prefect-worker.service` | Prefect worker polling `aqmesh-pool` |

These files are installed into `/etc/systemd/system/` by `deploy/bootstrap.sh` and are
**overwritten on every re-deploy**. Do not edit them on the VM.

## Operator-local overrides

To customise a unit without losing changes on the next re-deploy, use `systemctl edit`:

```bash
sudo systemctl edit prefect-worker    # or prefect-server
```

This creates a drop-in at `/etc/systemd/system/<unit>.service.d/override.conf` that is merged on
top of the shipped unit and is unaffected by re-deployment. For example, to set an extra
environment variable:

```ini
[Service]
Environment=MY_CUSTOM_VAR=value
```

After saving, apply the change:

```bash
sudo systemctl daemon-reload
sudo systemctl restart prefect-worker
```

See the full [deployment guide](../../docs/deployment.md#customising-unit-files) for the complete
configuration tier reference (credentials, shipped defaults, and operator overrides).
