"""Protocol tests for AMPS Fridge BLE."""

from custom_components.amps_fridge_ble_ha.api import FridgeApi, _to_signed_byte
from custom_components.amps_fridge_ble_ha.const import Request

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _api() -> FridgeApi:
    return FridgeApi(None, ADDRESS)  # type: ignore[arg-type]


def _status_payload(dual_zone: bool = False) -> bytes:
    payload = bytes(
        [
            1,
            1,
            0,
            2,
            4,
            20,
            236,
            2,
            1,
            0,
            0,
            0,
            0,
            0,
            5,
            87,
            12,
            6,
        ]
    )
    if dual_zone:
        payload += bytes([250, 10, 236, 2, 0, 0, 0, 0, 249, 1, 0, 3, 0])
    return payload


def _response_packet(api: FridgeApi, payload: bytes) -> bytes:
    packet = bytearray(b"\xfe\xfe")
    packet.append(len(payload) + 3)
    packet.append(Request.QUERY)
    packet.extend(payload)
    packet.extend(api._checksum(packet).to_bytes(2, "big"))
    return bytes(packet)


def test_signed_byte_conversion() -> None:
    assert _to_signed_byte(20) == 20
    assert _to_signed_byte(236) == -20


def test_known_query_and_bind_packets() -> None:
    api = _api()
    assert api._build_packet(Request.BIND) == b"\xfe\xfe\x03\x00\x01\xff"
    assert api._build_packet(Request.QUERY) == b"\xfe\xfe\x03\x01\x02\x00"


def test_decode_single_zone_status() -> None:
    api = _api()
    assert api._decode_status(_status_payload()) is True
    assert api.status["fridge_target"] == 4
    assert api.status["fridge_temp_min"] == -20
    assert api.status["bat_percent"] == 87
    assert "freezer_current" not in api.status


def test_decode_dual_zone_status() -> None:
    api = _api()
    assert api._decode_status(_status_payload(dual_zone=True)) is True
    assert api.status["freezer_target"] == -6
    assert api.status["freezer_temp_min"] == -20
    assert api.status["freezer_current"] == -7
    assert api.status["unknown_29"] == 3


def test_dual_zone_set_payload_preserves_range_and_footer() -> None:
    api = _api()
    api._decode_status(_status_payload(dual_zone=True))
    payload = api._build_set_other_payload({"locked": False})
    assert payload[15] == 10
    assert payload[16] == 236
    assert payload[-3:] == b"\x00\x03\x00"


def test_fragmented_notification_is_reassembled() -> None:
    api = _api()
    packet = _response_packet(api, _status_payload())
    midpoint = len(packet) // 2
    api._notification_handler(None, bytearray(packet[:midpoint]))
    assert not api._status_updated_event.is_set()
    api._notification_handler(None, bytearray(packet[midpoint:]))
    assert api._status_updated_event.is_set()
    assert api.status["bat_percent"] == 87


def test_bad_checksum_is_rejected() -> None:
    api = _api()
    packet = bytearray(_response_packet(api, _status_payload()))
    packet[-1] ^= 0xFF
    api._notification_handler(None, packet)
    assert not api._status_updated_event.is_set()
    assert api.status == {}
