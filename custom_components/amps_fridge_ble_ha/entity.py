"""Base entities for the AMPS Fridge BLE integration."""

from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from . import AmpsFridgeConfigEntry
from .api import FridgeApi
from .const import DOMAIN


class AmpsFridgeEntity(Entity):
    """Base class for AMPS Fridge entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: AmpsFridgeConfigEntry, api: FridgeApi) -> None:
        """Initialize the entity."""
        self.api = api
        self._address = entry.data[CONF_ADDRESS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data[CONF_NAME],
            manufacturer="AMPS",
        )

    @property
    def available(self) -> bool:
        """Return whether the fridge is available."""
        return self.api.is_available

    async def async_added_to_hass(self) -> None:
        """Subscribe to shared API updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._address}_update",
                self.async_write_ha_state,
            )
        )

    async def _async_refresh_after_write(self) -> None:
        """Refresh device state after a control write."""
        if await self.api.update_status():
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")
