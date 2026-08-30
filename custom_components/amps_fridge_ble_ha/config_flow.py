"""Config flow for AMPS Fridge BLE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import (
    DOMAIN,
    FRIDGE_NAME_PREFIXES,
    FRIDGE_SERVICE_UUID,
    GENERIC_SERVICE_UUID,
)

MANUAL_ENTRY = "manual"


def normalize_ble_address(addr: str) -> str | None:
    """Normalize a BLE address or return None when it is invalid."""
    compact = addr.replace("-", "").replace(":", "").strip().lower()
    if len(compact) != 12 or not all(c in "0123456789abcdef" for c in compact):
        return None
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


def is_supported_fridge(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Return True when an advertisement plausibly comes from a supported fridge.

    The fridge's own service UUID (0x1234) is specific enough to trust on its
    own. The 0xFFF0 service is a generic UUID shipped by countless cheap BLE
    modules, so it is only accepted alongside a known fridge name prefix.
    """
    uuids = {uuid.lower() for uuid in discovery_info.service_uuids}

    if FRIDGE_SERVICE_UUID in uuids:
        return True

    if GENERIC_SERVICE_UUID in uuids:
        name = (discovery_info.name or "").upper()
        return name.startswith(FRIDGE_NAME_PREFIXES)

    return False


class AmpsFridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AMPS Fridge BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        normalized_address = normalize_ble_address(discovery_info.address)
        if normalized_address is None:
            return self.async_abort(reason="invalid_address")

        if not is_supported_fridge(discovery_info):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(normalized_address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or normalized_address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a device found by Bluetooth discovery."""
        assert self._discovery_info is not None
        address = normalize_ble_address(self._discovery_info.address)
        assert address is not None
        default_name = self._discovery_info.name or address

        if user_input is not None:
            name = str(user_input.get(CONF_NAME) or default_name).strip() or address
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=default_name): str}
            ),
            description_placeholders={"name": default_name, "address": address},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from the fridges currently being advertised."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == MANUAL_ENTRY:
                return await self.async_step_manual()

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            name = self._discovered.get(address) or address
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        configured = self._async_current_ids()
        self._discovered = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            address = normalize_ble_address(info.address)
            if (
                address is None
                or address in configured
                or not is_supported_fridge(info)
            ):
                continue
            self._discovered[address] = info.name or address

        if not self._discovered:
            return await self.async_step_manual()

        choices: dict[str, str] = {
            address: f"{name} ({address})" for address, name in self._discovered.items()
        }
        choices[MANUAL_ENTRY] = "Enter a Bluetooth address manually"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a fridge by typing its Bluetooth address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_address = user_input.get(CONF_ADDRESS)
            normalized_address = (
                normalize_ble_address(raw_address)
                if isinstance(raw_address, str)
                else None
            )

            if normalized_address is None:
                errors["base"] = "invalid_address"
            else:
                name = str(user_input.get(CONF_NAME) or normalized_address).strip()
                if not name:
                    name = normalized_address

                await self.async_set_unique_id(
                    normalized_address, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={CONF_ADDRESS: normalized_address, CONF_NAME: name},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default=""): str,
                vol.Optional(CONF_NAME, default="AMPS Fridge"): str,
            }
        )

        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors,
        )
