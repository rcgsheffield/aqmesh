# AQMesh pipeline documentation

Operational documentation for running the AQMesh air-quality pipeline in production. For what the
pipeline does and how to run it locally, start with the [project README](../README.md).

| Document | Covers |
| --- | --- |
| [`architecture.md`](architecture.md) | System internals — source modules, infrastructure components, data layout, and design decisions. |
| [`deployment.md`](deployment.md) | Installing the pipeline on an Ubuntu 24.04 VM with `deploy/bootstrap.sh`, setting credentials, verifying the deployment, and **rolling out updates / upgrading Prefect**. |
| [`system-requirements.md`](system-requirements.md) | VM sizing — CPU, RAM, root disk, and the separately mounted data volume — and how the append-only data store grows. |
| [`service-management.md`](service-management.md) | Day-to-day service control — `systemctl` and `journalctl` commands, health checks, Prefect web UI access, schedule management, credential rotation, and common failure scenarios. |
| [`troubleshooting.md`](troubleshooting.md) | Operational issues seen in production and how to deal with them (e.g. SQLite `database is locked`). |
| [`publish.md`](publish.md) | Publishing a citable release — archiving each GitHub Release in **ORDA** (Sheffield's institutional repository) to mint a **DOI**, and the one-time token/variable setup. |

## New engineer: suggested reading order

If you're taking over this deployment or picking it up for the first time:

1. **[`architecture.md`](architecture.md)** — understand what the system does and how data flows
   through it end to end.
2. **[`system-requirements.md`](system-requirements.md)** — understand the VM the system runs on
   and the storage sizing assumptions.
3. **[`deployment.md`](deployment.md)** — understand how it was installed and how to roll out code
   updates.
4. **[`service-management.md`](service-management.md)** — learn day-to-day operations: starting
   and stopping services, reading logs, accessing the Prefect UI, rotating credentials.
5. **[`troubleshooting.md`](troubleshooting.md)** — skim the known failure modes so you recognise
   them if they occur.

## Quick reference

| Task | Document | Section |
| --- | --- | --- |
| Roll out a code update | [`deployment.md`](deployment.md) | [Rolling out updates](deployment.md#rolling-out-updates) |
| Rotate API credentials | [`service-management.md`](service-management.md) | [Credential rotation](service-management.md#credential-rotation) |
| Trigger a manual run | [`service-management.md`](service-management.md) | [Trigger a manual run](service-management.md#trigger-a-manual-run) |
| Access the Prefect UI | [`service-management.md`](service-management.md) | [Accessing the web UI remotely](service-management.md#accessing-the-web-ui-remotely-ssh-tunnel) |
| Worker keeps crashing | [`troubleshooting.md`](troubleshooting.md) | — |
| SQLite lock errors | [`troubleshooting.md`](troubleshooting.md) | [SQLite3OperationalError](troubleshooting.md#sqlite3operationalerror-database-is-locked) |
