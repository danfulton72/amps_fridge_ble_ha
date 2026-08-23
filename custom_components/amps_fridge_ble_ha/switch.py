"""Switch platform for the AMPS Fridge BLE integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
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
    """Set up the AMPS Fridge switch entity."""
    api: FridgeApi = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AmpsFridgeLockSwitch(entry, api)])


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
