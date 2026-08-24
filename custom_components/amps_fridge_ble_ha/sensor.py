"""Sensor platform for the AMPS Fridge BLE integration."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpsFridgeConfigEntry
from .entity import AmpsFridgeEntity

SENSORS: dict[str, dict[str, Any]] = {
    "battery_percent": {
        "name": "Battery",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "value_fn": lambda status: status.get("bat_percent"),
    },
    "battery_voltage": {
        "name": "Battery voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "value_fn": lambda status: (
            status.get("bat_vol_int", 0) + status.get("bat_vol_dec", 0) / 10
        ),
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpsFridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AMPS Fridge sensor entities."""
    api = entry.runtime_data.api
    async_add_entities(
        AmpsFridgeSensor(entry, api, key, definition)
        for key, definition in SENSORS.items()
    )


class AmpsFridgeSensor(AmpsFridgeEntity, SensorEntity):
    """Representation of an AMPS Fridge sensor."""

    def __init__(
        self,
        entry,
        api,
        sensor_key: str,
        sensor_def: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, api)
        self._sensor_def = sensor_def
        self._attr_unique_id = f"{self._address}_{sensor_key}"
        self._attr_name = sensor_def["name"]
        self._attr_device_class = sensor_def.get("device_class")
        self._attr_native_unit_of_measurement = sensor_def.get("unit")
        self._attr_state_class = sensor_def.get("state_class")
        self._attr_entity_category = sensor_def.get("entity_category")

    @property
    def native_value(self) -> float | int | None:
        """Return the current sensor value."""
        value_fn: Callable[[dict[str, Any]], Any] = self._sensor_def["value_fn"]
        return value_fn(self.api.status)
