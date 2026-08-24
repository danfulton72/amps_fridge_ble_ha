# AMPS Fridge BLE for Home Assistant

A Home Assistant custom integration for compatible AMPS, Alpicool, BrassMonkey, Ocean Comfort, and related 12 V/24 V portable fridges that use the same Bluetooth Low Energy protocol.

The protocol support in this repository has been verified against an AMPS F50. Other compatible models may expose a subset of the available entities.

## Features

- Local Bluetooth communication; no cloud account is required.
- Home Assistant Bluetooth discovery when a compatible service UUID is advertised.
- Bluetooth proxy support through Home Assistant's Bluetooth stack.
- Single- and dual-zone status detection.
- Climate entities for zone target/current temperature.
- A whole-fridge power switch.
- A control-panel lock switch.
- Battery percentage and voltage diagnostic sensors.
- Battery protection level selection.
- Fridge temperature range, hysteresis, and compressor start-delay controls.
- Freezer range controls when a dual-zone device reports them.

Power is intentionally represented as one whole-device switch. The underlying protocol exposes one shared power state, so presenting independent climate on/off controls for each zone would be misleading.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository with category **Integration**:
   `https://github.com/danfulton72/amps_fridge_ble_ha`
3. Search for **AMPS Fridge BLE** and install it.
4. Restart Home Assistant if HACS requests a restart.

You can also use the HACS repository shortcut:

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danfulton72&repository=amps_fridge_ble_ha&category=integration)

### Manual

1. Download a release from this repository.
2. Copy `custom_components/amps_fridge_ble_ha` into the `custom_components` directory in your Home Assistant configuration directory.
3. Restart Home Assistant.

## Configuration

Configuration is performed entirely from the Home Assistant UI.

1. Power on the fridge and ensure it is in Bluetooth range of Home Assistant or a Bluetooth proxy.
2. Go to **Settings > Devices & services**.
3. If the fridge is discovered, choose **Configure**.
4. Otherwise choose **Add Integration**, search for **AMPS Fridge BLE**, and enter the fridge Bluetooth address.

Bluetooth addresses may be entered using colons, hyphens, or as twelve hexadecimal characters. They are normalized internally to `XX:XX:XX:XX:XX:XX`.

Some fridge models require their APP/pairing control to be enabled before accepting a connection.

## Entities

A single-zone fridge normally exposes:

- `climate`: Fridge
- `switch`: Power
- `switch`: Lock
- `sensor`: Battery
- `sensor`: Battery voltage
- `select`: Battery saver
- `number`: Fridge max temperature
- `number`: Fridge min temperature
- `number`: Fridge hysteresis
- `number`: Start delay

When a second zone is reported by the device, the integration additionally exposes:

- `climate`: Freezer
- `number`: Freezer max temperature
- `number`: Freezer min temperature

The exact settings accepted by a fridge can vary by model.

## Bluetooth implementation

The integration uses Home Assistant's Bluetooth device resolution and `bleak-retry-connector` rather than starting its own scanner. This allows Home Assistant to select the best local adapter or Bluetooth proxy path for the device.

A single custom background polling task updates shared API state for all entities. It polls every 30 seconds while connected and retries every 60 seconds while disconnected. A temporary communication failure does not immediately mark the device unavailable: the last successful update timestamp is retained, and the integration only marks entities unavailable after five minutes without a successful status response. Control writes request an immediate status refresh so UI state is confirmed from the fridge rather than waiting for the next normal poll.

The protocol parser supports fragmented and concatenated BLE notifications and rejects packets with invalid checksums before they can overwrite entity state.

## Protocol notes

The AMPS F50 uses the same protocol family as several Alpicool-derived portable fridges. Important observed details include:

- Temperatures are signed 8-bit values.
- `BIND` and `QUERY` use fixed packet layouts.
- SET commands use a checksum over the packet body.
- Dual-zone SET payloads include independent freezer maximum/minimum temperature bytes.
- The observed dual-zone SET footer is `00 03 00`.
- SET responses may include an echoed command followed by a status packet.

Protocol behaviour has been inferred from real BLE captures. Please open an issue with a debug log and model number if another compatible fridge behaves differently.

## Development

The repository includes:

- HACS validation
- Home Assistant Hassfest validation
- Ruff linting
- Pytest protocol/config-flow helper tests
- Dependabot updates for GitHub Actions

Run the local checks with:

```bash
python -m pip install homeassistant pytest ruff
ruff check .
ruff format --check .
pytest -q
```

## Versioning

Releases use semantic versioning (`vMAJOR.MINOR.PATCH`). The integration manifest contains the matching version without the leading `v`.

## Credits

This project was originally derived from `Gruni22/alpicool_ha_ble` and builds on protocol investigation from `klightspeed/BrassMonkeyFridgeMonitor`.

## License

MIT License. See [LICENSE](LICENSE).
