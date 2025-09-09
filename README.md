# ABB Terra AC Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
![GitHub release](https://img.shields.io/github/v/release/JernejHren/ABB-Terra-AC)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This is a custom integration to connect and control ABB Terra AC EV chargers within Home Assistant. It communicates locally with the charger using the Modbus TCP protocol.

## Key Features
This integration creates the following entities in Home Assistant:
- **Sensors**: Charging State, Error Code, Cable Lock State, Active Power, Energy Delivered, and per-phase Current and Voltage (L1, L2, L3).
- **Switches**: To start/stop the charging session and to lock/unlock the charging cable.
- **Number Inputs**: To dynamically set the charging current limit (in Amperes) and configure a fallback limit.

---

## ⚠️ Important Information

- **Modbus TCP Only**: This integration works exclusively over **Modbus TCP** (via an Ethernet or WiFi connection). It does not support Modbus RTU (via RS485).
- **Single Active Connection**: The ABB Terra AC charger only allows **one active Modbus TCP session at a time**. Before using this integration, please ensure that no other applications or scripts (like diagnostic tools or other control systems) are connected to the charger. If another connection is active, this integration will fail to communicate.

---

## Charger Pre-configuration

Before adding the integration in Home Assistant, you must enable the Modbus TCP server on the charger itself. I used the official **TerraConfig** mobile app from ABB to do this.

1.  Connect to your charger using the TerraConfig app (usually via Bluetooth).
2.  Navigate to the charger's settings.
3.  Find the "Connectivity" menu or similar network settings.
4.  Enable the **Modbus TCP Server** option.
5.  Take note of the charger's IP address. I recommend setting a static IP address for the charger in your router's settings.
6.  The standard port for Modbus TCP is **502**, which is the default used by this integration.

---

## Installation

### Method 1: HACS (Recommended)

1.  In HACS, navigate to the "Integrations" tab.
2.  Click the three dots in the top-right corner and select "Custom repositories".
3.  In the repository field, enter this GitHub URL: `https://github.com/JernejHren/ABB-Terra-AC` and select "Integration" as the category. Click "Add".
4.  Search for "ABB Terra AC Modbus" in the list and click "Install".
5.  Restart Home Assistant.

### Method 2: Manual Installation

1.  Download the latest release from the [GitHub repository](https://github.com/JernejHren/ABB-Terra-AC).
2.  Copy the entire `abb_terra_ac` directory (containing all the integration files) into the `custom_components` folder inside your main Home Assistant configuration directory. If the `custom_components` folder doesn't exist, create it.
3.  The final path should look like this: `<config>/custom_components/abb_terra_ac/`.
4.  Restart Home Assistant.

---

## Configuration in Home Assistant

1.  Navigate to **Settings > Devices & Services**.
2.  Click the **Add Integration** button.
3.  Search for **ABB Terra AC Modbus**.
4.  Enter the IP address of your charger. You can leave the port at the default value of `502` unless you have changed it manually.
5.  After a successful setup, all entities related to the charger will appear in Home Assistant.

---

## Development Notes & Customizations

During the development of this integration, I discovered a few key differences between the official documentation and the actual behavior of my charger (tested on firmware `v1.8.32`). The integration is built to work with the charger's real-world behavior.

#### Charging State Register
- **The Problem:** The official Modbus documentation stated that the charging state (Idle, Plugged in, Charging) should be read from register `400Ch` (decimal `16396`). However, through extensive testing, I found that this register always returned a value of `0`.
- **The Solution:** By analyzing the raw data streams, I discovered that the actual charging state is reported in the adjacent register, **`400Dh` (decimal `16397`)**. Furthermore, the state code (0-5, corresponding to IEC 61851-1 states) is encoded in the high byte of this register's value. This integration is therefore hardcoded to read and decode this correct register to accurately reflect the charger's state.

#### Start/Stop Switch Logic
- **The Problem:** When sending a start/stop command, the switch entity in Home Assistant would flip back to its previous state. This was because the charger needs several seconds to process the command and update its state, but Home Assistant would read the old state too quickly.
- **The Solution:** The `Start/Stop Charging` switch in this integration now reflects the **active charging** state (`State C2`). After every `turn_on` or `turn_off` command is sent, the integration waits for 7 seconds before requesting a data refresh. This delay ensures that the charger has time to update its status, and the switch in the UI will correctly reflect the new state.

---

## License
This project is licensed under the Apache 2.0 License. See the `LICENSE` file for more details.
