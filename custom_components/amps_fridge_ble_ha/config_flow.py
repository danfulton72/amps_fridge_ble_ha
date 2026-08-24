"""Config flow for AMPS Fridge BLE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN


def normalize_ble_address(addr: str) -> str | None:
    """Normalize a BLE address or return None when it is invalid."""
    compact = addr.replace("-", "").replace(":", "").strip().lower()
    if len(compact) != 12 or not all(c in "0123456789abcdef" for c in compact):
        return None
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


class AmpsFridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AMPS Fridge BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        normalized_address = normalize_ble_address(discovery_info.address)
        if normalized_address is None:
            return self.async_abort(reason="invalid_address")

        await self.async_set_unique_id(normalized_address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or normalized_address
        }
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup or confirmation of a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_address = user_input.get(CONF_ADDRESS)
            normalized_address = (
                normalize_ble_address(raw_address) if isinstance(raw_address, str) else None
            )

            if normalized_address is None:
                errors["base"] = "invalid_address"
            else:
                name = str(user_input.get(CONF_NAME) or normalized_address).strip()
                if not name:
                    name = normalized_address

                await self.async_set_unique_id(normalized_address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={CONF_ADDRESS: normalized_address, CONF_NAME: name},
                )

        default_address = (
            normalize_ble_address(self._discovery_info.address)
            if self._discovery_info
            else None
        ) or ""
        default_name = (
            (self._discovery_info.name or default_address)
            if self._discovery_info
            else "AMPS Fridge"
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default=default_address): str,
                vol.Optional(CONF_NAME, default=default_name): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
