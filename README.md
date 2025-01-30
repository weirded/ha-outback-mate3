# Home Assistant Outback MATE3 Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

> **Warning**: This is an early release provided as-is. Works for me but YMMW. 

This custom component integrates the Outback MATE3 system controller with Home Assistant, providing real-time monitoring of Outback power system components including inverters and charge controllers.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weirded&repository=ha-outback-mate3&category=integration)

## Features

- Real-time monitoring of Outback MATE3 devices via UDP streaming
- Support for multiple inverters and charge controllers
- Energy monitoring compatible with Home Assistant's Energy Dashboard
- System-wide power and energy metrics
- Per-leg (L1/L2) power calculations for accurate monitoring

## Installation

### HACS (Recommended)

1. Click the HACS badge above to open HACS
2. Click on "Custom Repositories"
3. Add this repository URL and select "Integration" as the category
4. Install the "Outback MATE3" integration
5. Restart Home Assistant
3. Add the integration through the Home Assistant UI (Settings -> Devices & Services -> Add Integration -> Outback MATE3)

### Manual Installation
1. Copy the `custom_components/outback_mate3` directory to your Home Assistant configuration directory
2. Restart Home Assistant
3. Add the integration through the Home Assistant UI (Settings -> Devices & Services -> Add Integration -> Outback MATE3)

## Configuration

### MATE3 Setup

The integration uses the MATE3's UDP streaming protocol. You'll need to configure your MATE3 to send data to your Home Assistant instance:

##### On your MATE3 display:

<img width="333" alt="image" src="https://github.com/user-attachments/assets/901fe6d2-e2d2-4d18-b52b-91fd214d74fe" />

- Press the LOCK button
- Enter user code 141
- Navigate to Settings > System > Data Stream
- Ensure `Network Data Stream` shows `Enabled`
- Ensure `Destination IP` is the IP address of your Home Assistant instance
- Ensure `Destination Port` is the port you configured when installing the integration (`57027` by default)

You should now see your system and components in Home Assistant.

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
2. Check UDP port configuration
3. Ensure UDP streaming is enabled on MATE3
4. Check Home Assistant logs for any error messages

## Support

For bugs and feature requests, please open an issue on GitHub.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

[releases-shield]: https://img.shields.io/github/release/weirded/ha-outback-mate3.svg?style=for-the-badge
[releases]: https://github.com/weirded/ha-outback-mate3/releases
[license-shield]: https://img.shields.io/github/license/weirded/ha-outback-mate3.svg?style=for-the-badge
