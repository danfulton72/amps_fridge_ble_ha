"""API for AMPS fridges based on the shared Alpicool-family BLE protocol."""

import asyncio
import logging

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import FRIDGE_NOTIFY_UUID, FRIDGE_RW_CHARACTERISTIC_UUID, Request

_LOGGER = logging.getLogger(__name__)


def _to_signed_byte(b: int) -> int:
    """Convert an unsigned byte (0-255) to a signed byte (-128-127)."""
    return b - 256 if b > 127 else b


class FridgeApi:
    """A class to interact with the fridge."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the API."""
        self._hass = hass
        self._lock = asyncio.Lock()
        self.status = {}
        self._status_updated_event = asyncio.Event()
        self._bind_event = asyncio.Event()
        self._poll_task = None
        self._address = address
        # Created lazily in connect() via bleak_retry_connector.establish_connection,
        # which picks the best current path to the device (including through
        # Bluetooth proxies) and handles retries - rather than a single
        # BleakClient built once here and reused for the whole lifetime.
        self._client: BleakClient | None = None
        self._write_requires_response = False
        # Buffer for reassembling fragmented packets
        self._notification_buffer = bytearray()
        self.is_available: bool = True
        self._last_successful_update_time: float = 0.0

    def set_initial_timestamp(self) -> None:
        """Set the initial timestamp after a successful setup."""
        self._last_successful_update_time = asyncio.get_running_loop().time()

    def _checksum(self, data: bytes) -> int:
        """Calculate 2-byte big endian checksum."""
        return sum(data) & 0xFFFF

    def _build_set_other_payload(self, new_values: dict) -> bytes:
        """Build the complete payload for the setOther command."""
        current_status = self.status.copy()
        current_status.update(new_values)

        def to_unsigned_byte(x: int) -> int:
            return x & 0xFF

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
            freezer_zone_data = bytearray(
                [
                    to_unsigned_byte(current_status.get("freezer_target", 0)),
                    # Confirmed via BLE capture against a real AMPS/Alpicool-protocol
                    # fridge (F50): these two bytes are NOT padding. They are the
                    # freezer zone's settable max/min range (mirrors fridge_temp_max/
                    # fridge_temp_min for the fridge zone). Previously hardcoded to 0/0,
                    # which silently reset the freezer's configured range on
                    # every SET command (lock, power, temp, battery-saver, etc).
                    to_unsigned_byte(current_status.get("freezer_temp_max", 10)),
                    to_unsigned_byte(current_status.get("freezer_temp_min", -20)),
                    to_unsigned_byte(current_status.get("freezer_ret_diff", 1)),
                    to_unsigned_byte(current_status.get("freezer_tc_hot", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_mid", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_cold", 0)),
                    to_unsigned_byte(current_status.get("freezer_tc_halt", 0)),
                    # These three trailing bytes are still not understood, but a
                    # BLE capture of 13 real SET commands from the AMPS app -
                    # covering power, lock, run_mode, battery-saver, and both
                    # zones' temps/ranges - showed this exact 3-byte sequence
                    # (00 03 00) every single time, never 00 00 00 and never
                    # varying with any tested setting. Treating it as a fixed
                    # protocol constant rather than 0/0/0 padding or preserved
                    # status (it does NOT match the unrelated unknown_28/29/30
                    # fields reported in STATUS responses, which do vary).
                    0x00,
                    0x03,
                    0x00,
                ]
            )
            data.extend(freezer_zone_data)

        return data

    async def async_set_values(self, new_values: dict) -> None:
        """Public method to set configuration values."""
        if not self.status:
            _LOGGER.debug("Cannot set values, status is not available")
            return

        payload = self._build_set_other_payload(new_values)
        packet = self._build_packet(Request.SET, payload)
        await self._send_raw(packet)

    def _build_packet(self, cmd: int, data: bytes = b"") -> bytes:
        """Build a BLE command packet based on known working examples and protocol quirks."""
        if cmd == Request.BIND:
            return b"\xfe\xfe\x03\x00\x01\xff"
        if cmd == Request.QUERY:
            return b"\xfe\xfe\x03\x01\x02\x00"

        _LOGGER.debug("Using dynamic builder for cmd %s", cmd)

        header = b"\xfe\xfe"
        payload = bytearray([cmd])
        payload.extend(data)

        length = len(payload) + 2

        packet = bytearray(header)
        packet.append(length)
        packet.extend(payload)

        checksum = self._checksum(packet)
        packet.extend(checksum.to_bytes(2, "big"))

        _LOGGER.debug("Dynamically built packet for cmd %s: %s", cmd, packet.hex())
        return bytes(packet)

    async def async_set_temperature(self, zone: str, temp: int) -> None:
        """Public method to set the target temperature for a specific zone."""
        cmd = Request.SET_FRIDGE if zone == "fridge" else Request.SET_FREEZER
        payload = bytes([temp & 0xFF])

        packet = self._build_packet(cmd, payload)
        await self._send_raw(packet)

    def _decode_status(self, payload: bytes):
        """Decode query response payload for single or dual zone fridges."""
        try:
            base_status = {
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
            self.status.update(base_status)
            if len(payload) >= 28:
                dual_zone_status = {
                    "freezer_target": _to_signed_byte(payload[18]),
                    # Confirmed via BLE capture: these mirror temp_max/temp_min
                    # but for the freezer (right) zone, not unused padding.
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
                self.status.update(dual_zone_status)

            # Check for extra unknown fields at the end
            if len(payload) >= 31:
                extra_unknown_status = {
                    "unknown_28": payload[28],
                    "unknown_29": payload[29],
                    "unknown_30": payload[30],
                }
                self.status.update(extra_unknown_status)

            _LOGGER.debug("Decoded status: %s", self.status)
        except IndexError as e:
            _LOGGER.debug(
                "Failed to decode status payload (length %s): %s", len(payload), e
            )

    def _notification_handler(self, sender, data: bytearray):
        """Handle notifications, reassembling fragmented packets before parsing."""
        self._notification_buffer.extend(data)

        while self._notification_buffer:
            start_index = self._notification_buffer.find(b"\xfe\xfe")
            if start_index == -1:
                _LOGGER.debug(
                    "No packet header in buffer, clearing: %s",
                    self._notification_buffer.hex(),
                )
                self._notification_buffer.clear()
                return

            if start_index > 0:
                _LOGGER.debug(
                    "Discarding preamble: %s",
                    self._notification_buffer[:start_index].hex(),
                )
                self._notification_buffer = self._notification_buffer[start_index:]

            if len(self._notification_buffer) < 3:
                _LOGGER.debug("Buffer too short for length byte, waiting for more data")
                return

            packet_len_byte = self._notification_buffer[2]
            expected_total_len = 3 + packet_len_byte

            if len(self._notification_buffer) < expected_total_len:
                _LOGGER.debug(
                    "Incomplete packet. Have %s, need %s. Waiting for more data",
                    len(self._notification_buffer),
                    expected_total_len,
                )
                return

            current_packet = self._notification_buffer[:expected_total_len]
            self._notification_buffer = self._notification_buffer[expected_total_len:]

            _LOGGER.debug("<-- RECEIVED from %s: %s", sender, current_packet.hex())

            claimed_checksum = bytes(current_packet[-2:])
            computed_checksum = self._checksum(current_packet[:-2]).to_bytes(
                2, "big"
            )
            if claimed_checksum != computed_checksum:
                # A BLE notification occasionally arrives corrupted (dropped or
                # duplicated fragment, weak signal, a flaky BLE proxy, etc) -
                # confirmed against a real capture where a corrupted packet's
                # second half was a garbled repeat of its first half. Without
                # this check, that garbage gets decoded and silently overwrites
                # real entity state (e.g. a bogus 33 degC target) until the
                # next successful poll happens to correct it. Discard instead.
                _LOGGER.warning(
                    "Discarding packet with invalid checksum (claimed %s, "
                    "computed %s): %s",
                    claimed_checksum.hex(),
                    computed_checksum.hex(),
                    current_packet.hex(),
                )
                continue

            cmd = current_packet[3]
            payload = current_packet[4:]

            if cmd in [Request.QUERY]:
                self._decode_status(payload)
                self._status_updated_event.set()
            elif cmd == Request.BIND:
                self._bind_event.set()
            elif cmd in [Request.SET_FRIDGE, Request.SET_FREEZER, Request.SET]:
                _LOGGER.debug("Ignoring echo for SET command")
            else:
                _LOGGER.debug("Unhandled command in notification: %s", cmd)

    async def connect(self, is_reconnect: bool = False) -> bool:
        """Connect to the fridge and try to bind, with a fallback."""
        _LOGGER.debug("Attempting to connect")
        try:
            if not self._client or not self._client.is_connected:
                # Look up a fresh BLEDevice each attempt rather than caching one -
                # HA's Bluetooth stack tracks which adapter/proxy currently has
                # the best path to the device, which can change over time.
                ble_device = bluetooth.async_ble_device_from_address(
                    self._hass, self._address, connectable=True
                )
                if not ble_device:
                    _LOGGER.error(
                        "No connectable BLE device found for %s. Is it in "
                        "range of an adapter or Bluetooth proxy?",
                        self._address,
                    )
                    return False

                # establish_connection handles retries, backoff, and the
                # "already in progress" contention that can happen when
                # multiple integrations share the same Bluetooth adapter/
                # proxy - unlike calling BleakClient.connect() directly.
                self._client = await establish_connection(
                    BleakClient, ble_device, self._address
                )

            _LOGGER.debug("Discovering services and characteristics")
            write_char = None
            for service in self._client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == FRIDGE_RW_CHARACTERISTIC_UUID.lower():
                        write_char = char
                        break
                if write_char:
                    break

            if not write_char:
                _LOGGER.error(
                    "Write characteristic %s not found!", FRIDGE_RW_CHARACTERISTIC_UUID
                )
                await self.disconnect()
                return False

            if "write-without-response" in write_char.properties:
                self._write_requires_response = False
                _LOGGER.debug("Using 'write-without-response' for commands")
            elif "write" in write_char.properties:
                self._write_requires_response = True
                _LOGGER.debug(
                    "Device requires response for writes. Using 'write' for commands"
                )
            else:
                _LOGGER.error(
                    "Write characteristic %s has no usable write properties",
                    write_char.uuid,
                )
                await self.disconnect()
                return False

            await self._client.start_notify(
                FRIDGE_NOTIFY_UUID, self._notification_handler
            )

        except BleakError as e:
            _LOGGER.error("Failed to establish base BLE connection: %s", e)
            await self.disconnect()
            return False
        if not is_reconnect:
            _LOGGER.debug("Base BLE connection successful. Attempting to bind")
            try:
                self._bind_event.clear()
                bind_packet = self._build_packet(Request.BIND, b"\x01")
                await self._send_raw(bind_packet)

                await asyncio.wait_for(self._bind_event.wait(), timeout=20)
                _LOGGER.debug("Bind successful")
            except TimeoutError:
                _LOGGER.debug(
                    "Bind command timed out. Proceeding without binding. This may work for some models"
                )
            except BleakError as e:
                _LOGGER.debug(
                    "An error occurred during bind, proceeding without it: %s", e
                )
        else:
            _LOGGER.debug("Skipping bind process for reconnect")

        if self._client.is_connected:
            return True

        _LOGGER.debug("Connection is not active after connect attempt")
        return False

    @property
    def _is_connected(self) -> bool:
        """Return True if we have a live BLE connection."""
        return self._client is not None and self._client.is_connected

    async def disconnect(self):
        """Disconnect from the fridge."""
        if self._poll_task:
            self._poll_task.cancel()
        if self._is_connected:
            await self._client.disconnect()

    async def _send_raw(self, packet: bytes):
        """Send raw packet to fridge, adapting write method."""
        if not self._is_connected:
            _LOGGER.debug("Cannot send, not connected")
            return
        _LOGGER.debug("--> SENDING: %s", packet.hex())
        await self._client.write_gatt_char(
            FRIDGE_RW_CHARACTERISTIC_UUID,
            packet,
            response=self._write_requires_response,
        )

    async def update_status(self) -> bool:
        """Request status and wait for notification. Returns True on success, False on timeout."""
        if not self._is_connected:
            _LOGGER.debug("Cannot update status, not connected")
            return False

        self._status_updated_event.clear()
        await self._send_raw(self._build_packet(Request.QUERY, b"\x02"))
        try:
            await asyncio.wait_for(self._status_updated_event.wait(), timeout=5)
        except TimeoutError:
            _LOGGER.debug("Timeout waiting for status update")
            return False
        else:
            return True

    async def start_polling(self, update_callback):
        """Start polling for status updates in the background."""
        _LOGGER.debug("Starting background polling")
        if self._last_successful_update_time == 0.0:
            self._last_successful_update_time = asyncio.get_running_loop().time()
        while True:
            try:
                if not self._is_connected:
                    _LOGGER.debug("Device disconnected, attempting to reconnect")
                    if await self.connect(is_reconnect=True):
                        _LOGGER.debug("Successfully reconnected to device")
                        self.is_available = True
                        self._last_successful_update_time = (
                            asyncio.get_running_loop().time()
                        )
                    else:
                        _LOGGER.debug("Reconnect failed. Will retry later")
                if self._is_connected:
                    if await self.update_status():
                        self._last_successful_update_time = (
                            asyncio.get_running_loop().time()
                        )
                        if not self.is_available:
                            _LOGGER.debug("Device communication restored")
                            self.is_available = True
                time_since_success = (
                    asyncio.get_running_loop().time()
                    - self._last_successful_update_time
                )
                if time_since_success > 300:  # 5 minutes
                    if self.is_available:
                        _LOGGER.debug(
                            "Device has been unreachable for over 5 minutes. Marking as unavailable"
                        )
                        self.is_available = False
                        self.status.clear()
                update_callback()

                # --- Sleep ---
                sleep_duration = 30 if self._is_connected else 60
                await asyncio.sleep(sleep_duration)

            except asyncio.CancelledError:
                _LOGGER.debug("Polling task cancelled")
                self.is_available = False
                break
            except BleakError as e:
                _LOGGER.debug("An unexpected BLE error occurred during polling: %s", e)
                self.is_available = False
                await asyncio.sleep(60)
