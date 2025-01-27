# Outback MATE3 Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]

A Home Assistant integration for the Outback MATE3 system controller.

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weirded&repository=ha-outback-mate3&category=integration)

1. Click the button above or manually add `https://github.com/weirded/ha-outback-mate3` as a custom repository in HACS
2. Click Install
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/outback_mate3` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Outback MATE3"
4. Enter the IP address and port (default: 57027) of your MATE3

## Available Sensors

### Inverter Sensors
Each inverter in your system will have the following sensors:

- Current (A)
- Charger Current (A)
- Grid Current (A)
- Grid Voltage (V)
- Output Voltage (V)
- Power (W)
- Charger Power (W)
- Grid Power (W)
- Operating Mode (text)
- AC Mode (text)

### Charge Controller Sensors
Each charge controller in your system will have the following sensors:

- Solar Current (A)
- Solar Voltage (V)
- Battery Voltage (V)
- Solar Power (W)
- Charge Mode (text)

## Troubleshooting

If you're not seeing any sensors:
1. Check that your MATE3 is accessible at the configured IP address and port
2. Check the Home Assistant logs for any error messages
3. Make sure your MATE3 is sending data (you should see messages in the logs)

## Support

Please open an issue on GitHub if you encounter any problems or have feature requests.

[releases-shield]: https://img.shields.io/github/release/weirded/ha-outback-mate3.svg
[releases]: https://github.com/weirded/ha-outback-mate3/releases
