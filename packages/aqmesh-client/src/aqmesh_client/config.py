"""Configuration for the AQMesh API client.

These settings are read from environment variables (and an optional ``.env`` file)
so the same code runs unchanged locally and on the production VM. They cover only
what :class:`aqmesh_client.client.AQMeshClient` needs to talk to the API; the
pipeline's :class:`aqmesh_pipeline.config.Settings` subclasses this to add its own
data-layout settings.
"""

from __future__ import annotations

from typing import Literal

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base URLs from the AQMesh API manual (section 1.3).
BASE_URLS: dict[str, str] = {
    "test": "https://apitest.aqmeshdata.net/api",
    "prod": "https://api.aqmeshdata.net/api",
}


class APISettings(BaseSettings):
    """Environment-driven configuration for the AQMesh API client."""

    model_config = SettingsConfigDict(
        env_prefix="AQMESH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    username: str
    password: SecretStr
    environment: Literal["test", "prod"] = "test"

    # Reading request defaults (API manual section 4.10).
    units: str = "01"
    tpc: int = 1
    # The LocationData/Next route rejects a trailing /{version} segment, so the
    # client omits it when version is 0 (the default). Set non-zero only if a
    # future endpoint genuinely requires the 5th segment.
    version: int = 0

    request_timeout: float = 60.0
    max_retries: int = 4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def base_url(self) -> str:
        """Full API base URL for the selected environment."""
        return BASE_URLS[self.environment]
