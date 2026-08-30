"""Constants for the AMPS Fridge BLE integration."""

from enum import IntEnum

DOMAIN = "amps_fridge_ble_ha"

# Advertised service UUIDs used for discovery matching.
FRIDGE_SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"
# Generic UUID used by many unrelated cheap BLE modules - only trusted when the
# advertised name also matches one of the known fridge prefixes below.
GENERIC_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
# Compared against the uppercased advertised name.
FRIDGE_NAME_PREFIXES = ("WT-", "A1-", "AK1-", "AK2-", "AK3-")

FRIDGE_RW_CHARACTERISTIC_UUID = "00001235-0000-1000-8000-00805f9b34fb"
FRIDGE_NOTIFY_UUID = "00001236-0000-1000-8000-00805f9b34fb"


class Request:
    """Possible Commands."""

    BIND = 0x00
    QUERY = 0x01
    SET = 0x02
    RESET = 0x04
    SET_FRIDGE = 0x05
    SET_FREEZER = 0x06


# Response codes
class Response(IntEnum):
    """Message Response Codes."""

    STATUS = 0x01
    BATTERY = 0x02


# Battery protection levels
class BatteryProtection(IntEnum):
    """Battery Protection Levels."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
