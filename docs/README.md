# AQMesh pipeline documentation

Operational documentation for running the AQMesh air-quality pipeline in production. For what the
pipeline does and how to run it locally, start with the [project README](../README.md).

| Document | Covers |
| --- | --- |
| [`deployment.md`](deployment.md) | Installing the pipeline on an Ubuntu 24.04 VM with `deploy/bootstrap.sh`, setting credentials, verifying the deployment, and **rolling out updates / upgrading Prefect**. |
| [`system-requirements.md`](system-requirements.md) | VM sizing — CPU, RAM, root disk, and the separately mounted data volume — and how the append-only data store grows. |

New to the deployment? Read `system-requirements.md` to size the VM, then follow `deployment.md`
top to bottom. To ship a change to an already-running VM, jump straight to
[Rolling out updates](deployment.md#rolling-out-updates).
