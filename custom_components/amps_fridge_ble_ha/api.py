"""API for AMPS fridges based on the shared Alpicool-family BLE protocol."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import FRIDGE_NOTIFY_UUID, FRIDGE_RW_CHARACTERISTIC_UUID, Request

_LOGGER = logging.getLogger(__name__)


def _to_signed_byte(value: int) -> int:
    """Convert an unsigned byte (0-255) to a signed byte (-128-127)."""
    return value - 256 if value > 127 else value


class FridgeApi:
    """Interact with an AMPS/Alpicool-family fridge over BLE."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the API."""
        self._hass = hass
        self._address = address
        self._lock = asyncio.Lock()
        self._status_updated_event = asyncio.Event()
        self._bind_event = asyncio.Event()
        self._client: BleakClient | None = None
        self._write_requires_response = False
        self._notification_buffer = bytearray()
        self._has_connected_once = False
        self.status: dict[str, Any] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return the module logger for coordinator logging."""
        return _LOGGER

    @property
    def is_connected(self) -> bool:
        """Return whether a live BLE connection exists."""
        return self._client is not None and self._client.is_connected

    @property
    def has_connected_once(self) -> bool:
        """Return whether initial binding has already been attempted."""
        return self._has_connected_once

    @staticmethod
    def _checksum(data: bytes | bytearray) -> int:
        """Calculate the two-byte big-endian checksum."""
        return sum(data) & 0xFFFF

    def _build_set_other_payload(self, new_values: dict[str, Any]) -> bytes:
        """Build the complete payload for the SET command."""
        current_status = self.status.copy()
        current_status.update(new_values)

        def to_unsigned_byte(value: int) -> int:
            return value & 0xFF

        data = bytearray(
            [
                int(current_status.get("locked", 0)),
                int(current_status.get("powered_on", 1)),
                int(current_status.get("run_mode", 0)),
                int(current_status.get("bat_saver", 0)),
                to_unsigned_byte(current_status.get("fridge_target", 0)),
                to_unsigned_byte(current_status.get("fridge_temp_max", 20)),
                to_unsigned_byte(current_status.get("fridge_temp_min", -20)),
                to_unsigned_byte(current_status.get("fridge_ret_diff", 1)),
                int(current_status.get("start_delay", 0)),
                int(current_status.get("unit", 0)),
                to_unsigned_byte(current_status.get("fridge_tc_hot", 0)),
                to_unsigned_byte(current_status.get("fridge_tc_mid", 0)),
                to_unsigned_byte(current_status.get("fridge_tc_cold", 0)),
                to_unsigned_byte(current_status.get("fridge_tc_halt", 0)),
            ]
        )

        if "freezer_current" in current_status:
            data.extend(
                [
                    to_unsigned_byte(current_status.get("freezer_target", 0)),
                    to_unsigned_byte(current_status.get("freezer_temp_max", 10)),
                    to_unsigned_byte(current_status.get("freezer_temp_min", -20)),
                    to_unsigned_byte(current_status.get("freezer_ret_diff", 1)),
                    to_unsigned_byte(current_status.get("freezer_tc_hot", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_mid", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_cold", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_halt", 0)),
                    0x00,
                    0x03,
                    0x00,
                ]
            )

        return bytes(data)

    async def async_set_values(self, new_values: dict[str, Any]) -> None:
        """Set configuration values."""
        if not self.status:
            raise BleakError("Cannot write settings before status is available")

        await self._send_raw(
            self._build_packet(Request.SET, self._build_set_other_payload(new_values))
        )

    def _build_packet(self, cmd: int, data: bytes = b"") -> bytes:
        """Build a BLE command packet, including known protocol quirks."""
        if cmd == Request.BIND:
            return b"\xfe\xfe\x03\x00\x01\xff"
        if cmd == Request.QUERY:
            return b"\xfe\xfe\x03\x01\x02\x00"

        payload = bytearray([cmd])
        payload.extend(data)
        packet = bytearray(b"\xfe\xfe")
        packet.append(len(payload) + 2)
        packet.extend(payload)
        packet.extend(self._checksum(packet).to_bytes(2, "big"))
        return bytes(packet)

    async def async_set_temperature(self, zone: str, temp: int) -> None:
        """Set the target temperature for one zone."""
        if zone not in {"fridge", "freezer"}:
            raise ValueError(f"Unsupported fridge zone: {zone}")
        cmd = Request.SET_FRIDGE if zone == "fridge" else Request.SET_FREEZER
        await self._send_raw(self._build_packet(cmd, bytes([temp & 0xFF])))

    def _decode_status(self, payload: bytes) -> bool:
        """Decode a query response payload for single- or dual-zone fridges."""
        if len(payload) < 18:
            _LOGGER.debug("Ignoring short status payload of %s bytes", len(payload))
            return False

        status: dict[str, Any] = {
            "locked": bool(payload[0]),
            "powered_on": bool(payload[1]),
            "run_mode": payload[2],
            "bat_saver": payload[3],
            "fridge_target": _to_signed_byte(payload[4]),
            "fridge_temp_max": _to_signed_byte(payload[5]),
            "fridge_temp_min": _to_signed_byte(payload[6]),
            "fridge_ret_diff": _to_signed_byte(payload[7]),
            "start_delay": payload[8],
            "unit": payload[9],
            "fridge_tc_hot": _to_signed_byte(payload[10]),
            "fridge_tc_mid": _to_signed_byte(payload[11]),
            "fridge_tc_cold": _to_signed_byte(payload[12]),
            "fridge_tc_halt": _to_signed_byte(payload[13]),
            "fridge_current": _to_signed_byte(payload[14]),
            "bat_percent": payload[15],
            "bat_vol_int": payload[16],
            "bat_vol_dec": payload[17],
        }

        if len(payload) >= 28:
            status.update(
                {
                    "freezer_target": _to_signed_byte(payload[18]),
                    "freezer_temp_max": _to_signed_byte(payload[19]),
                    "freezer_temp_min": _to_signed_byte(payload[20]),
                    "freezer_ret_diff": _to_signed_byte(payload[21]),
                    "freezer_tc_hot": _to_signed_byte(payload[22]),
                    "freezer_tc_mid": _to_signed_byte(payload[23]),
                    "freezer_tc_cold": _to_signed_byte(payload[24]),
                    "freezer_tc_halt": _to_signed_byte(payload[25]),
                    "freezer_current": _to_signed_byte(payload[26]),
                    "running_status": payload[27],
                }
            )

        if len(payload) >= 31:
            status.update(
                {
                    "unknown_28": payload[28],
                    "unknown_29": payload[29],
                    "unknown_30": payload[30],
                }
            )

        self.status = status
        return True

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Reassemble fragmented notifications and parse complete packets."""
        self._notification_buffer.extend(data)

        while self._notification_buffer:
            start_index = self._notification_buffer.find(b"\xfe\xfe")
            if start_index == -1:
                self._notification_buffer.clear()
                return
            if start_index:
                del self._notification_buffer[:start_index]

            if len(self._notification_buffer) < 3:
                return

            expected_total_len = 3 + self._notification_buffer[2]
            if len(self._notification_buffer) < expected_total_len:
                return

            current_packet = bytes(self._notification_buffer[:expected_total_len])
            del self._notification_buffer[:expected_total_len]

            claimed_checksum = current_packet[-2:]
            computed_checksum = self._checksum(current_packet[:-2]).to_bytes(2, "big")
            if claimed_checksum != computed_checksum:
                _LOGGER.warning("Discarding BLE packet with an invalid checksum")
                continue

            cmd = current_packet[3]
            payload = current_packet[4:-2]

            if cmd == Request.QUERY:
                if self._decode_status(payload):
                    self._status_updated_event.set()
            elif cmd == Request.BIND:
                self._bind_event.set()
            elif cmd not in {Request.SET_FRIDGE, Request.SET_FREEZER, Request.SET}:
                _LOGGER.debug("Unhandled command in notification: %s", cmd)

    async def connect(self, is_reconnect: bool = False) -> bool:
        """Connect to the fridge and bind on the initial connection."""
        if self.is_connected:
            return True

        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            return False

        try:
            self._client = await establish_connection(
                BleakClient, ble_device, self._address
            )

            write_char = next(
                (
                    char
                    for service in self._client.services
                    for char in service.characteristics
                    if char.uuid.lower() == FRIDGE_RW_CHARACTERISTIC_UUID.lower()
                ),
                None,
            )
            if write_char is None:
                await self.disconnect()
                return False

            if "write-without-response" in write_char.properties:
                self._write_requires_response = False
            elif "write" in write_char.properties:
                self._write_requires_response = True
            else:
                await self.disconnect()
                return False

            await self._client.start_notify(FRIDGE_NOTIFY_UUID, self._notification_handler)

            if not is_reconnect:
                self._bind_event.clear()
                await self._send_raw(self._build_packet(Request.BIND))
                try:
                    await asyncio.wait_for(self._bind_event.wait(), timeout=20)
                except TimeoutError:
                    _LOGGER.debug("Bind timed out; continuing for compatible models")

            self._has_connected_once = True
            return self.is_connected
        except BleakError:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Disconnect from the fridge."""
        client = self._client
        self._client = None
        self._notification_buffer.clear()
        if client is not None and client.is_connected:
            await client.disconnect()

    async def _send_raw(self, packet: bytes) -> None:
        """Send a raw packet, serializing writes and adapting write method."""
        if not self.is_connected or self._client is None:
            raise BleakError("Fridge is not connected")

        async with self._lock:
            await self._client.write_gatt_char(
                FRIDGE_RW_CHARACTERISTIC_UUID,
                packet,
                response=self._write_requires_response,
            )

    async def update_status(self) -> bool:
        """Request status and wait for a valid notification."""
        if not self.is_connected:
            return False

        self._status_updated_event.clear()
        await self._send_raw(self._build_packet(Request.QUERY))
        try:
            await asyncio.wait_for(self._status_updated_event.wait(), timeout=5)
        except TimeoutError:
            return False
        return True
