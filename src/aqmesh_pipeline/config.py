"""Runtime configuration for the AQMesh pipeline.

Settings are read from environment variables (and an optional ``.env`` file) so the
same code runs unchanged locally and on the production VM. See ``.env.example``.

The API-client settings (credentials, base URL, request defaults) live in
:class:`aqmesh_client.config.APISettings`; :class:`Settings` extends it with the
pipeline's data-layout settings so a single object drives both the client and the flows.
"""

from __future__ import annotations

from pathlib import Path

from aqmesh_client.config import BASE_URLS, APISettings

__all__ = ["BASE_URLS", "Settings", "get_settings"]


class Settings(APISettings):
    """Environment-driven configuration for the full pipeline."""

    data_root: Path = Path("./data")

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "raw"

    @property
    def clean_dir(self) -> Path:
        return self.data_root / "clean"

    @property
    def resampled_dir(self) -> Path:
        return self.data_root / "resampled"

    @property
    def state_dir(self) -> Path:
        return self.data_root / "state"


def get_settings() -> Settings:
    """Load settings from the environment.

    Kept as a function (rather than a module-level singleton) so tests can set
    environment variables before construction.
    """
    return Settings()  # type: ignore[call-arg]
