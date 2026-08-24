"""Climate entity tests for AMPS Fridge BLE."""

from custom_components.amps_fridge_ble_ha.climate import _zone_temperature_limits


def test_fridge_climate_uses_device_min_max() -> None:
    """Fridge climate limits should reflect the values reported by the device."""
    status = {"fridge_temp_min": -18, "fridge_temp_max": 12}

    assert _zone_temperature_limits(status, "fridge") == (-18.0, 12.0)


def test_freezer_climate_uses_device_min_max() -> None:
    """Freezer climate limits should be independent from the fridge limits."""
    status = {
        "fridge_temp_min": -18,
        "fridge_temp_max": 12,
        "freezer_temp_min": -25,
        "freezer_temp_max": -2,
    }

    assert _zone_temperature_limits(status, "freezer") == (-25.0, -2.0)


def test_climate_limits_have_safe_defaults() -> None:
    """Climate entities should expose sensible limits before values are reported."""
    assert _zone_temperature_limits({}, "fridge") == (-20.0, 20.0)
