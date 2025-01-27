# Outback MATE3 Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Monitor your Outback Power Systems MATE3 controller in Home Assistant. This integration receives UDP streaming data directly from your MATE3 controller, providing real-time insights into your solar power system's performance.

## Features

### Inverter Monitoring
- Real-time power output monitoring
- L1 and L2 current, voltage, and power metrics
- Charging and buying/selling current tracking
- Inverter mode and AC source status
- Detailed operational state information

### Charge Controller Monitoring
- PV array current, voltage, and power
- Battery charging metrics
- Real-time charging mode status
- Output current monitoring

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
4. Enter the UDP port number (default: 57027)

### MATE3 Configuration

1. Access your MATE3 controller's web interface
2. Navigate to the Data Stream configuration
3. Enable UDP streaming
4. Set the destination IP to your Home Assistant IP address
5. Set the port to match your configuration (default: 57027)

## Available Sensors

### Combined System Metrics
- Total Grid Power (W)
- Total Grid Current (A)
- Total Charger Power (W)
- Total Charger Current (A)
- Total Inverter Power (W)
- Total Inverter Current (A)
- Total Charge Controller Output Current (A)
- Total Charge Controller Output Power (W)
- Average AC Input Voltage (V)
- Average AC Output Voltage (V)
- Average Battery Voltage (V)

### Inverter Sensors
Each inverter in your system will have:
- Current (A)
- Charger Current (A)
- Grid Current (A)
- AC Input Voltage (V)
- AC Output Voltage (V)
- Inverter Power (W)
- Charger Power (W)
- Grid Power (W)
- Inverter Mode
- AC Mode (no-ac, ac-drop, ac-use)
- Grid Mode (grid, generator)
- Battery Voltage (V)

### Charge Controller Sensors
Each charge controller will have:
- PV Current (A)
- PV Voltage (V)
- PV Power (W)
- Output Current (A)
- Battery Voltage (V)
- Charge Mode
- Output Power (W)

## Energy Dashboard Integration

This integration supports the Home Assistant Energy Dashboard with the following metrics:
- Grid Power Import/Export
- Solar Production
- Total Energy Monitoring

## Troubleshooting

If you're not seeing any data:
1. Check that your MATE3 is accessible at the configured IP address and port
2. Check the Home Assistant logs for any error messages
3. Make sure your MATE3 is sending data (you should see messages in the logs)

## Support

Please open an issue on GitHub if you encounter any problems or have feature requests.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Credits

- Outback Power Systems for their excellent documentation on the MATE3 data stream protocol
- The Home Assistant community for their continued support and inspiration

[releases-shield]: https://img.shields.io/github/v/release/weirded/ha-outback-mate3?style=flat
[releases]: https://github.com/weirded/ha-outback-mate3/releases
