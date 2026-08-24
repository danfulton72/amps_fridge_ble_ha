"""Data update coordinator for AMPS Fridge BLE."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FridgeApi

UPDATE_INTERVAL = timedelta(seconds=30)


class AmpsFridgeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate BLE connectivity and shared fridge status updates."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: FridgeApi
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=api.logger,
            name="AMPS Fridge BLE",
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest status from the fridge."""
        try:
            if not self.api.is_connected and not await self.api.connect(
                is_reconnect=self.api.has_connected_once
            ):
                raise UpdateFailed("Unable to connect to the fridge")

            if not await self.api.update_status():
                await self.api.disconnect()
                raise UpdateFailed("Timed out waiting for fridge status")
        except BleakError as err:
            await self.api.disconnect()
            raise UpdateFailed(f"Bluetooth communication failed: {err}") from err

        return dict(self.api.status)

    async def async_write_and_refresh(self, values: dict[str, Any]) -> None:
        """Write configuration values and refresh state immediately."""
        await self.api.async_set_values(values)
        await self.async_request_refresh()

    async def async_set_temperature_and_refresh(self, zone: str, temp: int) -> None:
        """Set a zone target temperature and refresh state immediately."""
        await self.api.async_set_temperature(zone, temp)
        await self.async_request_refresh()
