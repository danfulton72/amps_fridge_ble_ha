"""Switch platform for the AMPS Fridge BLE integration."""

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FridgeApi
from .const import DOMAIN
from .entity import AmpsFridgeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AMPS Fridge switch entities."""
    api: FridgeApi = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AmpsFridgePowerSwitch(entry, api),
            AmpsFridgeLockSwitch(entry, api),
        ]
    )


class AmpsFridgePowerSwitch(AmpsFridgeEntity, SwitchEntity):
    """Representation of the AMPS Fridge whole-unit power switch.

    powered_on is a single status field shared by both zones on the
    protocol side - there's no separate on/off per zone. Rather than
    exposing that through each zone's climate hvac_mode (which was
    confusing, since turning one zone's climate "off" silently powered
    off the other zone too), it's a single dedicated switch here.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, api: FridgeApi) -> None:
        """Initialize the switch."""
        super().__init__(entry, api)
        self._attr_unique_id = f"{self._address}_power"
        self._attr_name = f"{entry.data['name']} Power"

    @property
    def is_on(self) -> bool | None:
        """Return true if the fridge is powered on."""
        if not self.available:
            return None
        return self.api.status.get("powered_on", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fridge on."""
        await self.api.async_set_values({"powered_on": True})
        await asyncio.sleep(0.5)
        if await self.api.update_status():
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fridge off."""
        await self.api.async_set_values({"powered_on": False})
        await asyncio.sleep(0.5)
        if await self.api.update_status():
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")


class AmpsFridgeLockSwitch(AmpsFridgeEntity, SwitchEntity):
    """Representation of the AMPS Fridge lock switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, api: FridgeApi) -> None:
        """Initialize the switch."""
        super().__init__(entry, api)
        self._attr_unique_id = f"{self._address}_lock"
        self._attr_name = f"{entry.data['name']} Lock"

    @property
    def is_on(self) -> bool | None:
        """Return true if the lock is on."""
        if not self.available:
            return None
        return self.api.status.get("locked", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lock on."""
        await self.api.async_set_values({"locked": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lock off."""
        await self.api.async_set_values({"locked": False})
