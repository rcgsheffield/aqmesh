# aqmesh-client

A dependency-light Python client for the [AQMesh](https://www.aqmesh.com/) air-quality
monitoring REST API. Depends only on `httpx` and `pydantic`/`pydantic-settings` — no
Prefect, pandas, or pipeline machinery — so it's suitable for scripts, notebooks, or
other tools that just need to talk to the API.

## Installation

```bash
pip install aqmesh
```

## Usage

```python
from aqmesh_client import AQMeshClient, APISettings

settings = APISettings()  # reads AQMESH_USERNAME / AQMESH_PASSWORD / AQMESH_ENVIRONMENT
client = AQMeshClient(settings)
assets = client.get_assets()
```

## Command-line interface

Installing the package also installs an `aqmesh-client` console script for exercising
the API directly from a shell or notebook. Config comes from the same environment
variables as the Python API (`AQMESH_USERNAME`, `AQMESH_PASSWORD`, `AQMESH_ENVIRONMENT`),
read from the environment or a `.env` file.

Every command prints JSON to stdout (add `--pretty` for indented output); progress and
error messages go to stderr, so stdout stays pipeable. A non-zero exit means
authentication failed or the API was unreachable — an empty result (`[]`/`{}`) is not
an error.

```bash
aqmesh-client ping                        # server health — no credentials required
aqmesh-client assets --pretty              # pods/locations visible to this account
aqmesh-client sensors --active             # sensor status + failed sensors
aqmesh-client notifications                # operator notices
aqmesh-client fetch 510 gas                # one page of unread readings
aqmesh-client fetch 510 gas --all          # drain every unread batch
aqmesh-client repeat 510 particle          # re-fetch the last delivered batch
```

This is a read-only inspection tool. For scheduling, storage, and the full data
pipeline, see the [`aqmesh` CLI](https://github.com/rcgsheffield/aqmesh#commands).

This package is extracted from and consumed by the
[AQMesh data pipeline](https://github.com/rcgsheffield/aqmesh) — see that repo's
[API reference docs](https://github.com/rcgsheffield/aqmesh/tree/main/docs/api-reference)
for full endpoint documentation.
