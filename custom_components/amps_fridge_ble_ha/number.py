"""Number platform for the AMPS Fridge BLE integration."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FridgeApi
from .const import DOMAIN
from .entity import AmpsFridgeEntity

_LOGGER = logging.getLogger(__name__)

NUMBERS = {
    "left_ret_diff": {
        "name": "Hysteresis",
        "min": 1,
        "max": 10,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": "°C",
    },
    "start_delay": {
        "name": "Start Delay",
        "min": 0,
        "max": 10,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": "min",
    },
}

# Only present on dual-zone (fridge/freezer) models. Confirmed via BLE capture
# against a real AMPS/Alpicool-protocol fridge (F50): these are the freezer
# zone's own settable temperature range, separate from the left zone's
# temp_max/temp_min. Range bounds below are generous defaults (-30 to 15);
# tighten them if your model's app UI shows a narrower allowed range.
DUAL_ZONE_NUMBERS = {
    "right_temp_max": {
        "name": "Freezer Max Temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": "°C",
    },
    "right_temp_min": {
        "name": "Freezer Min Temperature",
        "min": -30,
        "max": 15,
        "step": 1,
        "mode": NumberMode.SLIDER,
        "unit": "°C",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AMPS Fridge number entities."""
    api: FridgeApi = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AmpsFridgeNumber(entry, api, number_key, number_def)
        for number_key, number_def in NUMBERS.items()
    ]

    if "right_current" in api.status:
        _LOGGER.debug("Dual-zone fridge detected, adding freezer range entities")
        entities.extend(
            AmpsFridgeNumber(entry, api, number_key, number_def)
            for number_key, number_def in DUAL_ZONE_NUMBERS.items()
        )

    async_add_entities(entities)


class AmpsFridgeNumber(AmpsFridgeEntity, NumberEntity):
    """Representation of an AMPS Fridge Number entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry: ConfigEntry, api: FridgeApi, number_key: str, number_def: dict
    ) -> None:
        """Initialize the number entity."""
        super().__init__(entry, api)
        self._number_key = number_key
        self._number_def = number_def

        self._attr_unique_id = f"{self._address}_{self._number_key}"
        self._attr_name = f"{entry.data['name']} {self._number_def['name']}"
        self._attr_native_min_value = self._number_def["min"]
        self._attr_native_max_value = self._number_def["max"]
        self._attr_native_step = self._number_def["step"]
        self._attr_mode = self._number_def["mode"]
        self._attr_native_unit_of_measurement = self._number_def.get("unit")

    @property
    def native_value(self) -> float | None:
        """Return the state of the number entity."""
        if not self.available:
            return None
        return self.api.status.get(self._number_key)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.api.async_set_values({self._number_key: int(value)})
