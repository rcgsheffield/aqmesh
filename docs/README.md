# AQMesh pipeline documentation

Operational documentation for running the AQMesh air-quality pipeline in production. For what the
pipeline does and how to run it locally, start with the [project README](../README.md).

| Document | Covers |
| --- | --- |
| [`deployment.md`](deployment.md) | Installing the pipeline on an Ubuntu 24.04 VM with `deploy/bootstrap.sh`, setting credentials, verifying the deployment, and **rolling out updates / upgrading Prefect**. |
| [`system-requirements.md`](system-requirements.md) | VM sizing — CPU, RAM, root disk, and the separately mounted data volume — and how the append-only data store grows. |
| [`prefect-ui.md`](prefect-ui.md) | The built-in Prefect web UI — what it shows, and how to reach it over an SSH tunnel (the server is bound to localhost). |
| [`troubleshooting.md`](troubleshooting.md) | Operational issues seen in production and how to deal with them (e.g. SQLite `database is locked`). |

New to the deployment? Read `system-requirements.md` to size the VM, then follow `deployment.md`
top to bottom. To ship a change to an already-running VM, jump straight to
[Rolling out updates](deployment.md#rolling-out-updates). To watch runs in a browser, see
[`prefect-ui.md`](prefect-ui.md).
