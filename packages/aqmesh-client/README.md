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

This package is extracted from and consumed by the
[AQMesh data pipeline](https://github.com/rcgsheffield/aqmesh) — see that repo's
[API reference docs](https://github.com/rcgsheffield/aqmesh/tree/main/docs/api-reference)
for full endpoint documentation.
