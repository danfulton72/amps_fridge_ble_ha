"""Climate platform for the AMPS Fridge BLE integration."""

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpsFridgeConfigEntry
from .entity import AmpsFridgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpsFridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities from coordinator data."""
    coordinator = entry.runtime_data.coordinator
    entities = [AmpsFridgeClimateZone(entry, coordinator, "fridge")]
    if "freezer_current" in coordinator.data:
        entities.append(AmpsFridgeClimateZone(entry, coordinator, "freezer"))
    async_add_entities(entities)


class AmpsFridgeClimateZone(AmpsFridgeEntity, ClimateEntity):
    """Representation of one cooling zone."""

    _attr_hvac_modes = [HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, entry, coordinator, zone: str) -> None:
        """Initialize a climate zone."""
        super().__init__(entry, coordinator)
        self._zone = zone
        self._attr_unique_id = f"{self._address}_{zone}"
        self._attr_name = zone.capitalize()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the only supported HVAC mode."""
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Return the current zone temperature."""
        return self.coordinator.data.get(f"{self._zone}_current")

    @property
    def target_temperature(self) -> float | None:
        """Return the target zone temperature."""
        return self.coordinator.data.get(f"{self._zone}_target")

    @property
    def min_temp(self) -> float:
        """Return the configured minimum target temperature."""
        return float(self.coordinator.data.get(f"{self._zone}_temp_min", -20))

    @property
    def max_temp(self) -> float:
        """Return the configured maximum target temperature."""
        return float(self.coordinator.data.get(f"{self._zone}_temp_max", 20))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        await self.coordinator.async_set_temperature_and_refresh(
            self._zone, int(kwargs[ATTR_TEMPERATURE])
        )
