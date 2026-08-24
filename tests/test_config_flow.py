"""Tests for the AMPS Fridge BLE config flow."""

from custom_components.amps_fridge_ble_ha.config_flow import normalize_ble_address


def test_normalize_ble_address() -> None:
    """Valid BLE addresses are normalized to uppercase colon format."""
    assert normalize_ble_address("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_ble_address("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_ble_address("aabbccddeeff") == "AA:BB:CC:DD:EE:FF"


def test_reject_invalid_ble_address() -> None:
    """Malformed BLE addresses are rejected."""
    assert normalize_ble_address("") is None
    assert normalize_ble_address("AA:BB:CC") is None
    assert normalize_ble_address("GG:BB:CC:DD:EE:FF") is None
