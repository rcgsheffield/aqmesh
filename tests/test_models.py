"""Tests for Param/Asset helpers: pod hardware-mismatch detection (issue #64)."""

from __future__ import annotations

from aqmesh_client.models import Asset, Param


def test_param_other():
    assert Param.GAS.other is Param.PARTICLE
    assert Param.PARTICLE.other is Param.GAS


def test_lacks_param_hardware_particle_only_pod():
    asset = Asset(
        location_number=4971,
        last_gas_reading_number=0,
        last_particle_reading_number=740546364,
    )
    assert asset.lacks_param_hardware(Param.GAS) is True
    assert asset.lacks_param_hardware(Param.PARTICLE) is False


def test_lacks_param_hardware_gas_only_pod():
    asset = Asset(
        location_number=1,
        last_gas_reading_number=555,
        last_particle_reading_number=0,
    )
    assert asset.lacks_param_hardware(Param.PARTICLE) is True
    assert asset.lacks_param_hardware(Param.GAS) is False


def test_lacks_param_hardware_dead_pod_not_flagged():
    # Both counters unset (issue #65's location 4975) must NOT read as a hardware mismatch.
    asset = Asset(location_number=4975)
    assert asset.lacks_param_hardware(Param.GAS) is False
    assert asset.lacks_param_hardware(Param.PARTICLE) is False


def test_lacks_param_hardware_healthy_pod_not_flagged():
    asset = Asset(
        location_number=510,
        last_gas_reading_number=3200000,
        last_particle_reading_number=15000000,
    )
    assert asset.lacks_param_hardware(Param.GAS) is False
    assert asset.lacks_param_hardware(Param.PARTICLE) is False
