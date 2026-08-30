"""Tests for the AMPS Fridge BLE config flow."""

from types import SimpleNamespace

from custom_components.amps_fridge_ble_ha.config_flow import (
    is_supported_fridge,
    normalize_ble_address,
)

FRIDGE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
GENERIC_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"


def _advert(name: str | None, *uuids: str) -> SimpleNamespace:
    """Build a minimal stand-in for BluetoothServiceInfoBleak."""
    return SimpleNamespace(
        name=name, address="AA:BB:CC:DD:EE:FF", service_uuids=list(uuids)
    )


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


def test_fridge_service_uuid_is_trusted_alone() -> None:
    """The fridge's own service UUID is specific enough on its own."""
    assert is_supported_fridge(_advert("WT-0001", FRIDGE_UUID))
    assert is_supported_fridge(_advert("Some Rebadged Fridge", FRIDGE_UUID))


def test_generic_uuid_requires_known_name_prefix() -> None:
    """0xFFF0 only counts when the advertised name looks like a fridge."""
    assert is_supported_fridge(_advert("WT-0001", GENERIC_UUID))
    assert is_supported_fridge(_advert("AK3-1234", GENERIC_UUID))
    assert is_supported_fridge(_advert("a1-2436", GENERIC_UUID))


def test_unrelated_fff0_devices_are_rejected() -> None:
    """Cheap BLE modules that reuse 0xFFF0 must not be offered as fridges."""
    assert not is_supported_fridge(_advert("LEDBlue-12345", GENERIC_UUID))
    assert not is_supported_fridge(_advert("Govee_H5075", GENERIC_UUID))
    assert not is_supported_fridge(_advert(None, GENERIC_UUID))


def test_unknown_services_are_rejected() -> None:
    """Adverts without either service UUID never match."""
    assert not is_supported_fridge(
        _advert("WT-0001", "0000180f-0000-1000-8000-00805f9b34fb")
    )
    assert not is_supported_fridge(_advert("WT-0001"))
