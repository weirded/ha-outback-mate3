# Home Assistant Outback MATE3 Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

> ⚠️ **Version 2.0 is a breaking change.** The integration now works on Home Assistant OS but requires installing a companion add-on in addition to the integration. See the updated installation steps below.

> This is an early release provided as-is. Works for me but YMMW.

This project integrates the Outback MATE3 system controller with Home Assistant, providing real-time monitoring of Outback power system components including inverters and charge controllers. It ships as two pieces that work together:

- **Add-on** (`outback_mate3`): listens for MATE3 UDP streaming telemetry on the LAN, parses it, and exposes a WebSocket stream of parsed device state. Runs on Home Assistant OS / Supervised.
- **Integration** (`custom_components/outback_mate3`): connects to the add-on's WebSocket and creates / updates HA sensor entities. Installed via HACS.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weirded&repository=ha-outback-mate3&category=integration)

## Features

- Real-time monitoring of Outback MATE3 devices via UDP streaming
- Works on Home Assistant OS (via the add-on) and Supervised installs
- Support for multiple inverters and charge controllers
- Energy monitoring compatible with Home Assistant's Energy Dashboard
- System-wide power and energy metrics
- Per-leg (L1/L2) power calculations for accurate monitoring

## Installation

You need both the add-on and the integration.

### 1. Install the add-on

1. Go to **Settings → Add-ons → Add-on Store**
2. Click the **⋮ menu → Repositories**, add `https://github.com/weirded/ha-outback-mate3`, and reload
3. Find the **Outback MATE3** add-on in the store and install it
4. Start the add-on (the default options — UDP port 57027, WS port 8099 — work out of the box)

### 2. Install the integration (HACS)

1. Open HACS → **Integrations**
2. **⋮ menu → Custom repositories**, add this repo URL with category **Integration**
3. Install **Outback MATE3** and restart Home Assistant
4. Add the integration: **Settings → Devices & Services → Add Integration → Outback MATE3**
5. The default WebSocket URL assumes the add-on is running on the same instance; edit only if you've changed the add-on's WS port

### Manual installation (integration only)

Copy `custom_components/outback_mate3/` into your Home Assistant config directory. You still need the add-on installed separately.

## Configuration

### MATE3 Setup

The add-on uses the MATE3's UDP streaming protocol. Configure your MATE3 to send data to your Home Assistant host:

##### On your MATE3 display:

<img width="333" alt="image" src="https://github.com/user-attachments/assets/901fe6d2-e2d2-4d18-b52b-91fd214d74fe" />

- Press the LOCK button
- Enter user code 141
- Navigate to Settings > System > Data Stream
- Ensure `Network Data Stream` shows `Enabled`
- Ensure `Destination IP` is the IP address of your Home Assistant instance
- Ensure `Destination Port` matches the add-on's `udp_port` option (default `57027`)

You should now see your system and components in Home Assistant.

## Upgrading from 1.x

The 1.x integration bound a UDP socket inside the Home Assistant core container, which does not work on HA OS. Version 2.0 moves UDP listening into a separate add-on and reduces the integration to a WebSocket client. To upgrade:

1. Install the add-on as above.
2. Update the integration via HACS to 2.0 or later.
3. The integration will migrate your existing config entry automatically. If the default add-on URL doesn't resolve on your setup, edit the integration's configuration to set the correct WebSocket URL.
4. Entity unique IDs are preserved, so your existing dashboards, automations, and Energy Dashboard configuration continue to work.

## Available Sensors

### System Device
Combined metrics for your entire Outback system:
- From Grid (W) - Power from/to grid (positive = consumption, negative = production)
- Solar Production (W) - Total solar production
- From Battery (W) - Battery power flow (positive = discharge, negative = charge)
- To Loads (W) - Total power to loads (From Grid + From Battery)
- Battery Voltage (V) - System battery voltage (averaged from charge controllers)
- Solar Production Energy (kWh) - Daily solar production

### Inverter Device
Per-inverter metrics:
- L1/L2 Grid Power (W) - Power from/to grid per leg
- L1/L2 Inverter Power (W) - Inverter output power per leg
- L1/L2 Charger Power (W) - Charger input power per leg
- L1/L2 AC Input Voltage (V) - AC input voltage per leg
- L1/L2 AC Output Voltage (V) - AC output voltage per leg
- L1/L2 Buy Current (A) - Grid buy current per leg
- L1/L2 Sell Current (A) - Grid sell current per leg

### Charge Controller Device
Per-charge controller metrics:
- PV Current (A)
- PV Voltage (V)
- Output Current (A)
- Output Power (W)
- Battery Voltage (V)
- Daily kWh

## Energy Dashboard Setup

To use this integration with Home Assistant's Energy Dashboard:

1. Go to Settings -> Energy
2. Add the following sensors:
   - Grid consumption/production: "From Grid" (handles both consumption and production)
   - Solar production: "Solar Production"
   - Home battery storage: "From Battery"

The integration will automatically track power values over time and calculate energy usage for the dashboard.

## Troubleshooting

If you're not seeing data:
1. Verify MATE3 network connectivity
2. Enable debug logging and check Home Assistant logs for any error messages

## Support

For bugs and feature requests, please open an issue on GitHub.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

[releases-shield]: https://img.shields.io/github/release/weirded/ha-outback-mate3.svg?style=for-the-badge
[releases]: https://github.com/weirded/ha-outback-mate3/releases
[license-shield]: https://img.shields.io/github/license/weirded/ha-outback-mate3.svg?style=for-the-badge
