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
from .const import DOMAIN, PRESET_ECO, PRESET_MAX
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
    """

    _attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = -20
    _attr_max_temp = 20
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_MAX, PRESET_ECO]

    def __init__(self, entry: ConfigEntry, api: FridgeApi, zone: str) -> None:
        """Initialize the climate entity for a specific zone ("fridge" or "freezer")."""
        super().__init__(entry, api)
        self._zone = zone

        self._attr_unique_id = f"{self._address}_{self._zone}"
        self._attr_name = f"{self._zone.capitalize()}"

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation."""
        return HVACMode.COOL if self.api.status.get("powered_on") else HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature for this zone."""
        return self.api.status.get(f"{self._zone}_current")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for this zone."""
        return self.api.status.get(f"{self._zone}_target")

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        run_mode = self.api.status.get("run_mode")
        return PRESET_ECO if run_mode == 1 else PRESET_MAX

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        is_on = hvac_mode == HVACMode.COOL
        await self.api.async_set_values({"powered_on": is_on})

        await asyncio.sleep(0.5)
        if await self.api.update_status():
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for this zone."""
        if ATTR_TEMPERATURE in kwargs:
            temp = int(kwargs[ATTR_TEMPERATURE])
            await self.api.async_set_temperature(self._zone, temp)

            await asyncio.sleep(0.5)
            if await self.api.update_status():
                async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        run_mode_value = 1 if preset_mode == PRESET_ECO else 0
        await self.api.async_set_values({"run_mode": run_mode_value})
        await asyncio.sleep(0.5)
        if await self.api.update_status():
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self._address}_update")
