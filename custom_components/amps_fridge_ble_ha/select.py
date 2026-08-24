"""Select platform for the AMPS Fridge BLE integration."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmpsFridgeConfigEntry
from .const import BatteryProtection
from .entity import AmpsFridgeEntity

BATTERY_SAVER_OPTIONS = [level.name.capitalize() for level in BatteryProtection]
BATTERY_SAVER_MAP = {
    level.name.capitalize(): level.value for level in BatteryProtection
}
BATTERY_SAVER_MAP_REV = {value: name for name, value in BATTERY_SAVER_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmpsFridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AMPS Fridge select entities."""
    async_add_entities(
        [AmpsFridgeBatterySaverSelect(entry, entry.runtime_data.coordinator)]
    )


class AmpsFridgeBatterySaverSelect(AmpsFridgeEntity, SelectEntity):
    """Battery protection level select."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = BATTERY_SAVER_OPTIONS
    _attr_name = "Battery saver"

    def __init__(self, entry, coordinator) -> None:
        """Initialize the select entity."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{self._address}_battery_saver"

    @property
    def current_option(self) -> str | None:
        """Return the selected battery protection level."""
        return BATTERY_SAVER_MAP_REV.get(self.coordinator.data.get("bat_saver"))

    async def async_select_option(self, option: str) -> None:
        """Change the selected battery protection level."""
        if option not in BATTERY_SAVER_MAP:
            raise ValueError(f"Unsupported battery saver option: {option}")
        await self.coordinator.async_write_and_refresh(
            {"bat_saver": BATTERY_SAVER_MAP[option]}
        )
