"""Base entities for the AMPS Fridge BLE integration."""

from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AmpsFridgeConfigEntry
from .const import DOMAIN
from .coordinator import AmpsFridgeCoordinator


class AmpsFridgeEntity(CoordinatorEntity[AmpsFridgeCoordinator]):
    """Base class for AMPS Fridge entities."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: AmpsFridgeConfigEntry, coordinator: AmpsFridgeCoordinator
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._address = entry.data[CONF_ADDRESS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.data[CONF_NAME],
            manufacturer="AMPS",
        )
