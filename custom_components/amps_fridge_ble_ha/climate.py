"""Climate platform for the AMPS Fridge BLE integration."""

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    """Set up the AMPS Fridge climate entities based on initial status."""
    api: FridgeApi = hass.data[DOMAIN][entry.entry_id]

    entities = [AmpsFridgeClimateZone(entry, api, "fridge")]

    if "freezer_current" in api.status:
        _LOGGER.debug("Dual-zone fridge detected, adding freezer zone entity")
        entities.append(AmpsFridgeClimateZone(entry, api, "freezer"))

    async_add_entities(entities)


class AmpsFridgeClimateZone(AmpsFridgeEntity, ClimateEntity):
    """Representation of an AMPS Fridge refrigerator zone.

    The AMPS F50 (and similar models) has a genuinely separate fridge
    compartment and freezer compartment - both cool independently and
    simultaneously, not a single compressor that switches between them.
    So unlike some other Alpicool-protocol fridges, there is no user
    configuration option here to opt into a "Fridge/Freezer mode switch"
    behavior - both zone entities are simply always available together.

    No Max/Eco preset mode either: this entity only exposes target
    temperature. Power for the whole unit (not per-zone - the fridge
    only has a single powered_on flag shared by both zones) is a
    separate switch entity instead of climate's hvac_mode on/off,
    since toggling one zone's climate "off" was silently powering off
    the other zone too. Allowed operating range (min/max) per zone is
    configured separately via number entities.
    """

    _attr_hvac_modes = [HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, entry: ConfigEntry, api: FridgeApi, zone: str) -> None:
        """Initialize the climate entity for a specific zone ("fridge" or "freezer")."""
        super().__init__(entry, api)
        self._zone = zone

        self._attr_unique_id = f"{self._address}_{self._zone}"
        self._attr_name = f"{self._zone.capitalize()}"

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation. Cool is the only supported mode; power is a separate switch."""
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature for this zone."""
        return self.api.status.get(f"{self._zone}_current")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for this zone."""
        return self.api.status.get(f"{self._zone}_target")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for this zone."""
        if ATTR_TEMPERATURE in kwargs:
            temp = int(kwargs[ATTR_TEMPERATURE])
            await self.api.async_set_temperature(self._zone, temp)

            await asyncio.sleep(0.5)
            if await self.api.update_status():
                async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")
