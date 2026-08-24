"""Switch platform for the AMPS Fridge BLE integration."""

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpsFridgeConfigEntry
from .entity import AmpsFridgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpsFridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AMPS Fridge switch entities."""
    api = entry.runtime_data.api
    async_add_entities(
        [AmpsFridgePowerSwitch(entry, api), AmpsFridgeLockSwitch(entry, api)]
    )


class AmpsFridgePowerSwitch(AmpsFridgeEntity, SwitchEntity):
    """Whole-unit power switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Power"

    def __init__(self, entry, api) -> None:
        """Initialize the power switch."""
        super().__init__(entry, api)
        self._attr_unique_id = f"{self._address}_power"

    @property
    def is_on(self) -> bool | None:
        """Return whether the fridge is powered on."""
        return self.api.status.get("powered_on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fridge on."""
        await self.api.async_set_values({"powered_on": True})
        await self._async_refresh_after_write()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fridge off."""
        await self.api.async_set_values({"powered_on": False})
        await self._async_refresh_after_write()


class AmpsFridgeLockSwitch(AmpsFridgeEntity, SwitchEntity):
    """Control-panel lock switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Lock"

    def __init__(self, entry, api) -> None:
        """Initialize the lock switch."""
        super().__init__(entry, api)
        self._attr_unique_id = f"{self._address}_lock"

    @property
    def is_on(self) -> bool | None:
        """Return whether the control panel is locked."""
        return self.api.status.get("locked")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the control-panel lock."""
        await self.api.async_set_values({"locked": True})
        await self._async_refresh_after_write()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the control-panel lock."""
        await self.api.async_set_values({"locked": False})
        await self._async_refresh_after_write()
