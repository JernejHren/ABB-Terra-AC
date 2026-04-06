# ABB Terra AC Modbus

Home Assistant custom integration for ABB Terra AC EV chargers using Modbus TCP.

This integration connects directly to a charger over the local network and polls a single Modbus register block for charger status, measurements, and control values. It is intended for ABB Terra AC chargers that expose the documented Modbus TCP interface.

## Session pause vs stop

**To pause charging while keeping the session alive**, set **Charging Current Limit** to **0 A**. The charger follows IEC 61851-1 minimum current behaviour and will not end the session the way a **Stop Charging** command does.

**Stop Charging** ends the session on the charger side. Depending on vehicle and charger behaviour, **starting again may require a new start command** after a stop.

## Features

- UI-based setup through Home Assistant config flow
- UI-based reconfiguration when the charger IP address or port changes
- Local polling over Modbus TCP
- Charger device in the Home Assistant device registry
- Sensors for:
  - charging state (raw register value)
  - derived session state (idle, active, paused by current vs command, etc.)
  - last start/stop command issued from Home Assistant
  - error code
  - socket lock state
  - active power
  - session energy
  - phase currents L1-L3
  - phase voltages L1-L3
  - actual current limit
  - serial number
  - firmware version
- Switches for:
  - start/stop charging
  - cable lock/unlock
- Number entities for:
  - charging current limit
  - fallback current limit

Serial number and firmware version sensors are disabled by default in the entity registry.

## Supported devices

This integration is intended for ABB Terra AC chargers that expose the Modbus TCP register layout used by this project.

It is currently designed around:

- ABB Terra AC chargers with an LCD display, where Modbus TCP is available
- ABB Terra AC wallbox models with local Modbus TCP access
- A single charger device per Home Assistant config entry
- Installations where Home Assistant can reach the charger directly on the local network
- A charger setup where Modbus TCP is enabled on the charger side

ABB Terra AC chargers without an LCD display are not supported by this integration because they do not expose the Modbus TCP interface used here.

If your charger uses a different register map, a gateway, or a vendor-specific firmware variant with incompatible Modbus behavior, some entities may be unavailable or report incorrect values.

## Supported functions

The integration supports the following Home Assistant functions:

- Reading charger status, measurements, and identity information
- Starting and stopping charging
- Locking and unlocking the cable
- Setting the charging current limit
- Setting the fallback current limit
- Reconfiguring the charger connection from the Home Assistant UI

The integration does not currently support:

- Automatic discovery
- Multiple devices behind a single config entry
- Charger-side diagnostics downloads
- Firmware updates
- Custom Home Assistant services beyond the entity services exposed by button, switch, and number entities

## Installation

### HACS installation

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open the three-dot menu and select `Custom repositories`.
4. Add `https://github.com/JernejHren/ABB-Terra-AC` as an `Integration` repository.
5. Search for `ABB Terra AC Modbus` and install it.
6. Restart Home Assistant.
7. Open `Settings -> Devices & Services`.
8. Click `Add Integration`.
9. Search for `ABB Terra AC Modbus`.
10. Enter the charger IP address or hostname and confirm the Modbus TCP port.

### Manual installation

1. Copy `custom_components/abb_terra_ac` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Open `Settings -> Devices & Services`.
4. Click `Add Integration`.
5. Search for `ABB Terra AC Modbus`.
6. Enter the charger IP address or hostname.
7. Confirm the Modbus TCP port. The default is `502`.
8. Finish the setup.

During setup, the integration tests the TCP connection and performs a small Modbus read before creating the config entry.

### Installation parameters

The setup dialog asks for:

- `Host`: IP address or DNS name of the ABB Terra AC charger
- `Port`: Modbus TCP port exposed by the charger, usually `502`

## Configuration

This integration is configured from the Home Assistant UI.

You need:

- The IP address or hostname of the charger
- The Modbus TCP port, usually `502`

The integration creates one config entry per charger and uses `host:port` as its unique identifier.

### Configuration parameters

This integration currently supports the following user-configurable parameters through config flow:

- `host`
  The IP address or hostname Home Assistant uses to reach the charger over the local network.
- `port`
  The Modbus TCP port used for communication. In most installations this is `502`.

**Options** (under the integration’s **Configure** menu): **polling interval** (`scan_interval`) from 5 to 300 seconds. This does not change the charger IP or port.

If the charger IP address, hostname, or port changes, use the integration **reconfigure** flow to update the existing config entry without deleting it.
Remove and re-add the integration only if reconfiguration does not solve the problem.

## What the integration provides

After setup, Home Assistant creates one charger device and the supported entities listed above.

The integration polls a single 37-register holding-register block starting at address `16384` and refreshes data every 15 seconds by default.

## Data updates

The integration uses Home Assistant's `DataUpdateCoordinator` with local polling.

Current update behavior:

- Poll interval: every 15 seconds
- Transport: Modbus TCP over the local network
- Read strategy: one holding-register block read starting at address `16384`
- Update scope: one charger per config entry

If the charger becomes unreachable, entities become unavailable. When communication recovers, entities update automatically on the next successful poll.

Known implementation details:

- Charging state is derived from register `400Dh` high byte because the documented `400Ch` does not return a usable value on tested chargers.
- The integration contains a one-time recovery workaround for known charger firmware issues where fallback limit or charging current limit may reset to an invalid value after an unexpected reboot.

## Removal

To remove the integration:

1. Open `Settings -> Devices & Services`.
2. Open the `ABB Terra AC Modbus` integration entry.
3. Select the three-dot menu.
4. Click `Delete`.
5. Confirm the removal.

Removing the integration removes its entities and device from Home Assistant. It does not change configuration on the charger itself.

## Limitations

- This integration currently depends on manual setup. Automatic discovery is not implemented.
- It requires network access from Home Assistant to the charger over Modbus TCP.
- ABB Terra AC variants without an LCD display are not supported because this integration depends on Modbus TCP.
- The charger appears to allow only one active Modbus TCP client session at a time.
- Support is focused on ABB Terra AC chargers with compatible Modbus register behavior.
- The integration assumes a single charger device per config entry.
- Some charger states are derived from observed device behavior instead of documentation alone.
- Identity sensors are disabled by default because they are usually less relevant for day-to-day dashboards.
- On tested setups, Modbus TCP is tied to the charger's Ethernet-side connection rather than native charger Wi-Fi.
- Community reports suggest that Ethernet-to-Wi-Fi bridges or TCP/RS485 converters may work, but these setups are not officially tested by this integration.
- If the charger firmware behaves differently from the tested register layout, values may be missing or incorrect.

## Use cases

Typical use cases for this integration include:

- Monitoring whether a vehicle is plugged in, idle, charging, or paused
- Displaying charging current, voltage, power, and delivered energy on Home Assistant dashboards
- Starting or stopping charging from Home Assistant
- Locking the cable from Home Assistant after a vehicle is connected
- Applying charger current limits as part of automations or energy-management logic
- Tracking charger availability and troubleshooting communication issues

## Examples

Example automation ideas:

- Stop charging when total household power usage rises above a threshold
- Reduce the charger current limit during expensive tariff windows
- Notify when the charger reports an error code
- Show a badge when the charger becomes unavailable
- Lock the cable automatically when charging starts

Example dashboard cards:

- Charger status card with charging state, error code, and socket lock state
- Power and current graph for active charging sessions
- Controls for start/stop charging and current limit adjustment
- Diagnostic view with firmware version and serial number enabled when needed

## Troubleshooting

- Verify that the charger is reachable on the network from the Home Assistant host.
- Confirm that Modbus TCP is enabled and reachable on port `502` or the configured port.
- If the charger refuses or drops Modbus connections, make sure no other Modbus client is already connected.
- If you are trying to use charger Wi-Fi directly, review the charger communication setup first. Modbus TCP is documented and tested here as an Ethernet-side connection.
- If you use a Wi-Fi bridge or TCP/RS485 converter, treat that setup as community-supported rather than officially validated by this project.
- If setup fails with an invalid response, verify that the charger exposes the expected holding registers.
- If entities show as unavailable, check charger connectivity and whether the charger still responds to Modbus requests.
- If the charger IP address or Modbus port changed, use the integration reconfiguration flow in Home Assistant.
- If current-limit values look wrong after a charger reboot, review the charger state and Home Assistant logs to see whether the firmware recovery workaround was applied.
- If serial number or firmware version sensors do not appear, enable them manually in the entity registry because they are disabled by default.

## Project links

- Repository: `https://github.com/JernejHren/ABB-Terra-AC`
- Issue tracker: `https://github.com/JernejHren/ABB-Terra-AC/issues`
- Home Assistant community thread: `https://community.home-assistant.io/t/custom-integration-abb-terra-ac-ev-charger-modbus-tcp/929020`
