"""Data models and shared constants for AQMesh payloads.

The reading payloads are large and vary by firmware, so we deliberately keep the
reading models permissive (``extra="allow"``) and do the real work on pandas
DataFrames in :mod:`aqmesh_pipeline.transform`. The :class:`Asset` model is the one
we depend on structurally, because it drives the per-location download loop.
"""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, ConfigDict


class Param(IntEnum):
    """The ``Param`` path segment of the LocationData endpoint (manual 4.10)."""

    GAS = 1
    PARTICLE = 2

    @property
    def label(self) -> str:
        """Human/path-friendly name used in storage partitions."""
        return "gas" if self is Param.GAS else "particle"

    @property
    def reading_number_field(self) -> str:
        """Name of the unique per-reading identifier in this param's payload."""
        return "gas_reading_number" if self is Param.GAS else "particle_reading_number"


#: Timestamp field present on every reading payload.
READING_DATESTAMP_FIELD = "reading_datestamp"

#: Sentinel reading values that indicate the value cannot be used (manual 4.12).
#: These are converted to missing (NaN) during cleaning.
GAS_SENTINELS: frozenset[float] = frozenset(
    {-1000, -999, -998, -997, -996, -995, -994, -993, -992, -991}
)
PARTICLE_SENTINELS: frozenset[float] = frozenset({-1000, -893, -892})

#: Gas species carried in a gas reading. Each has ``<sp>_prescaled``,
#: ``<sp>_slope``, ``<sp>_offset``, ``<sp>_state`` and ``<sp>_units`` fields.
GAS_SPECIES: tuple[str, ...] = ("co", "no", "so2", "no2", "o3", "h2s", "eo")

#: Particulate channels. Each has ``<ch>_prescale``, ``<ch>_slope`` and
#: ``<ch>_offset`` fields. Note: prescale field is ``_prescale`` (no ``d``).
PARTICLE_CHANNELS: tuple[str, ...] = (
    "pm1",
    "pm2_5",
    "pm4",
    "pm10",
    "pm_tpc",
    "pm_total",
)


class Asset(BaseModel):
    """A pod at a location, as returned by ``/Pods/Assets_V1`` (manual 4.19)."""

    model_config = ConfigDict(extra="allow")

    location_number: int
    location_name: str | None = None
    serial_number: int | None = None
    firmware_version: str | None = None
    last_gas_reading_number: int | None = None
    last_particle_reading_number: int | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None


class ServerPing(BaseModel):
    """Server health snapshot from ``/serverping`` (manual 4.16).

    Useful as a liveness/freshness probe: ``most_recent_reading`` tells you how
    stale the upstream data is before a pipeline run trusts it.
    """

    model_config = ConfigDict(extra="allow")

    server_time: str | None = None
    last_sequence_number: int | None = None
    most_recent_reading: str | None = None
    last_communication: str | None = None
    most_recent_processed: str | None = None
    version: str | None = None


class SensorDetail(BaseModel):
    """A sensor's status and lifetime, from ``/sensor/SensorDetail`` (manual 4.20).

    ``replacement_needed`` carries a human-readable recommendation string (or null
    when the sensor is within its expected life), so its truthiness flags sensors
    worth attention.
    """

    model_config = ConfigDict(extra="allow")

    serial_number: int | None = None  # pod serial number
    sensor_serial_number: str | None = None
    sensor_type_name: str | None = None
    sensor_status_name: str | None = None
    pod_status_name: str | None = None
    age_in_months: int | None = None
    expiry_date: str | None = None
    replacement_needed: str | None = None


class FailedSensor(BaseModel):
    """A sensor that has tripped its fail criteria, from ``/Pods/SensorFail`` (manual 4.8)."""

    model_config = ConfigDict(extra="allow")

    sensor_serial_number: str | int | None = None
    pod_serial_number: int | None = None
    sensor_type: str | None = None
    fail_type: str | None = None
    fail_date: str | None = None
    status: str | None = None
