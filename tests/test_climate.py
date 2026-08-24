"""Tests for AMPS Fridge BLE climate entities."""

from types import SimpleNamespace

from homeassistant.const import CONF_ADDRESS, CONF_NAME

from custom_components.amps_fridge_ble_ha.api import FridgeApi
from custom_components.amps_fridge_ble_ha.climate import AmpsFridgeClimateZone

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _entry():
    """Return a minimal config-entry stand-in for entity construction."""
    return SimpleNamespace(data={CONF_ADDRESS: ADDRESS, CONF_NAME: "Test Fridge"})


def _api() -> FridgeApi:
    """Return an API instance without a running Home Assistant instance."""
    return FridgeApi(None, ADDRESS)  # type: ignore[arg-type]


def test_fridge_climate_uses_configured_temperature_limits() -> None:
    """The fridge climate range follows the device's configured min/max."""
    api = _api()
    api.status = {
        "fridge_current": 4,
        "fridge_target": 3,
        "fridge_temp_min": -8,
        "fridge_temp_max": 12,
    }
    entity = AmpsFridgeClimateZone(_entry(), api, "fridge")

    assert entity.min_temp == -8
    assert entity.max_temp == 12

    api.status["fridge_temp_min"] = -5
    api.status["fridge_temp_max"] = 8
    assert entity.min_temp == -5
    assert entity.max_temp == 8


def test_freezer_climate_uses_configured_temperature_limits() -> None:
    """The freezer climate range follows the device's configured min/max."""
    api = _api()
    api.status = {
        "freezer_current": -10,
        "freezer_target": -12,
        "freezer_temp_min": -20,
        "freezer_temp_max": -2,
    }
    entity = AmpsFridgeClimateZone(_entry(), api, "freezer")

    assert entity.min_temp == -20
    assert entity.max_temp == -2

    api.status["freezer_temp_min"] = -18
    api.status["freezer_temp_max"] = 0
    assert entity.min_temp == -18
    assert entity.max_temp == 0
