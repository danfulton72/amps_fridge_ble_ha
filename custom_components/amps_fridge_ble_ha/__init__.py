"""The AMPS Fridge BLE integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .api import FridgeApi
from .coordinator import AmpsFridgeCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class AmpsFridgeRuntimeData:
    """Runtime data for an AMPS Fridge config entry."""

    api: FridgeApi
    coordinator: AmpsFridgeCoordinator


AmpsFridgeConfigEntry = ConfigEntry[AmpsFridgeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AmpsFridgeConfigEntry) -> bool:
    """Set up AMPS Fridge BLE from a config entry."""
    api = FridgeApi(hass, entry.data[CONF_ADDRESS])
    coordinator = AmpsFridgeCoordinator(hass, entry, api)
    entry.runtime_data = AmpsFridgeRuntimeData(api=api, coordinator=coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmpsFridgeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.api.disconnect()
    return unload_ok
