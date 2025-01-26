# Outback MATE3 Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

![Outback Power](https://www.outbackpower.com/images/logo_outback.png)

Monitor and track your Outback Power Systems MATE3 controller in real-time through Home Assistant. This integration receives UDP streaming data directly from your MATE3 controller, providing detailed insights into your solar power system's performance.

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

## Prerequisites

1. An Outback Power Systems MATE3 controller
2. The MATE3 must be configured to stream data via UDP
3. Home Assistant installation
4. HACS (Home Assistant Community Store) installed

## Installation

### HACS Installation (Recommended)

1. Make sure you have [HACS](https://hacs.xyz) installed in your Home Assistant instance
2. Add this repository to HACS:
   - Click on HACS in the sidebar
   - Click on "Integrations"
   - Click the three dots in the top right corner
   - Select "Custom repositories"
   - Add the URL `https://github.com/weirded/ha-outback-mate3`
   - Select "Integration" as the category
   - Click "Add"
3. Click on "+ Explore & Download Repositories" in the bottom right
4. Search for "Outback MATE3"
5. Click "Download"
6. Restart Home Assistant
7. Go to Configuration > Integrations
8. Click the "+ ADD INTEGRATION" button
9. Search for "Outback MATE3"
10. Enter the UDP port number (default: 57027)

### Manual Installation

1. Download the latest release from the GitHub repository
2. Copy the `outback_mate3` folder from the zip to your Home Assistant's `custom_components` directory
3. Restart Home Assistant
4. Go to Configuration > Integrations
5. Click the "+ ADD INTEGRATION" button
6. Search for "Outback MATE3"
7. Enter the UDP port number (default: 57027)

## Configuration

The integration needs to be configured with:

- UDP Port: The port number that your MATE3 controller is streaming data to (default: 57027)

### MATE3 Configuration

To configure your MATE3 to stream data:

1. Access your MATE3 controller's web interface
2. Navigate to the Data Stream configuration
3. Enable UDP streaming
4. Set the destination IP to your Home Assistant IP address
5. Set the port to match your configuration (default: 57027)

## Available Entities

### Inverter Sensors
- Inverter current (L1 & L2)
- Charger current (L1 & L2)
- Buy current (L1 & L2)
- Sell current (L1 & L2)
- AC input voltage (L1 & L2)
- AC output voltage (L1 & L2)
- Output power
- Inverter mode
- AC mode

### Charge Controller Sensors
- PV current
- PV voltage
- PV power
- Output current
- Battery voltage
- Charger mode

## Troubleshooting

If you're not seeing any data:

1. Verify that your MATE3 is configured to stream data to the correct IP address and port
2. Check your firewall settings to ensure UDP traffic is allowed on the configured port
3. Check the Home Assistant logs for any error messages
4. Verify that your MATE3 is on the same network as your Home Assistant instance

## Support

For issues and feature requests, please [open an issue](https://github.com/weirded/ha-outback-mate3/issues) on the GitHub repository.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Credits

- Outback Power Systems for their excellent documentation on the MATE3 data stream protocol
- The Home Assistant community for their continued support and inspiration

[releases-shield]: https://img.shields.io/github/release/weirded/ha-outback-mate3.svg
[releases]: https://github.com/weirded/ha-outback-mate3/releases
[license-shield]: https://img.shields.io/github/license/weirded/ha-outback-mate3.svg
