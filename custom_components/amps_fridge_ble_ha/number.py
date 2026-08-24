"""Number platform for the AMPS Fridge BLE integration."""

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpsFridgeConfigEntry
from .entity import AmpsFridgeEntity

NUMBERS: dict[str, dict[str, Any]] = {
    "fridge_temp_max": {
        "name": "Fridge max temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTemperature.CELSIUS,
    },
    "fridge_temp_min": {
        "name": "Fridge min temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTemperature.CELSIUS,
    },
    "fridge_ret_diff": {
        "name": "Fridge hysteresis",
        "min": 1,
        "max": 10,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTemperature.CELSIUS,
    },
    "start_delay": {
        "name": "Start delay",
        "min": 0,
        "max": 10,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTime.MINUTES,
    },
}

DUAL_ZONE_NUMBERS: dict[str, dict[str, Any]] = {
    "freezer_temp_max": {
        "name": "Freezer max temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTemperature.CELSIUS,
    },
    "freezer_temp_min": {
        "name": "Freezer min temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": UnitOfTemperature.CELSIUS,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpsFridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AMPS Fridge number entities."""
    coordinator = entry.runtime_data.coordinator
    definitions = dict(NUMBERS)
    if "freezer_current" in coordinator.data:
        definitions.update(DUAL_ZONE_NUMBERS)
    async_add_entities(
        AmpsFridgeNumber(entry, coordinator, key, definition)
        for key, definition in definitions.items()
    )


class AmpsFridgeNumber(AmpsFridgeEntity, NumberEntity):
    """Representation of an AMPS Fridge numeric setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry,
        coordinator,
        number_key: str,
        number_def: dict[str, Any],
    ) -> None:
        """Initialize the number entity."""
        super().__init__(entry, coordinator)
        self._number_key = number_key
        self._attr_unique_id = f"{self._address}_{number_key}"
        self._attr_name = number_def["name"]
        self._attr_native_min_value = number_def["min"]
        self._attr_native_max_value = number_def["max"]
        self._attr_native_step = number_def["step"]
        self._attr_mode = number_def["mode"]
        self._attr_native_unit_of_measurement = number_def["unit"]

    @property
    def native_value(self) -> float | None:
        """Return the current setting."""
        return self.coordinator.data.get(self._number_key)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting and refresh state."""
        await self.coordinator.async_write_and_refresh({self._number_key: int(value)})
