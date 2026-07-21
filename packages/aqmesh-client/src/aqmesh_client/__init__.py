"""A thin, dependency-light client for the AQMesh REST API.

Depends only on ``httpx`` and ``pydantic``/``pydantic-settings`` — no Prefect, pandas,
or pipeline machinery — so it can be reused from scripts or notebooks that only need to
talk to the API.
"""

from __future__ import annotations

from .client import AQMeshAuthError, AQMeshClient
from .config import BASE_URLS, APISettings
from .models import Asset, FailedSensor, Param, SensorDetail, ServerPing

__version__ = "0.3.0"  # x-release-please-version

__all__ = [
    "__version__",
    "BASE_URLS",
    "APISettings",
    "AQMeshAuthError",
    "AQMeshClient",
    "Asset",
    "FailedSensor",
    "Param",
    "SensorDetail",
    "ServerPing",
]
