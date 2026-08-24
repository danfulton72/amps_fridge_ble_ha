"""The AMPS Fridge BLE integration."""

from __future__ import annotations

from dataclasses import dataclass

from bleak.exc import BleakError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import FridgeApi
from .const import DOMAIN

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


AmpsFridgeConfigEntry = ConfigEntry[AmpsFridgeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AmpsFridgeConfigEntry) -> bool:
    """Set up AMPS Fridge BLE from a config entry."""
    api = FridgeApi(hass, entry.data[CONF_ADDRESS])
    entry.runtime_data = AmpsFridgeRuntimeData(api=api)

    try:
        if not await api.connect():
            raise ConfigEntryNotReady("Could not connect to AMPS fridge")
        if not await api.update_status():
            raise ConfigEntryNotReady("Could not get initial AMPS fridge status")
    except BleakError as err:
        await api.disconnect()
        raise ConfigEntryNotReady(f"Failed to initialize AMPS fridge: {err}") from err

    api.set_initial_timestamp()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    address = entry.data[CONF_ADDRESS]
    entry.async_create_background_task(
        hass,
        api.start_polling(
            lambda: async_dispatcher_send(hass, f"{DOMAIN}_{address}_update")
        ),
        name="amps_fridge_ble_poll",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmpsFridgeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.api.disconnect()
    return unload_ok
