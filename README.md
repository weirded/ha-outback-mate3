# Home Assistant Outback MATE3 Integration

This Home Assistant integration allows you to monitor your Outback Power Systems MATE3 controller via UDP streaming data. It supports both inverters and charge controllers.

## Features

- Real-time monitoring of Outback Radian inverters:
  - L1 and L2 inverter current, voltage, and power
  - Charging and buying/selling current
  - Inverter mode and AC source status
  - Output power

- Real-time monitoring of Outback charge controllers:
  - PV current, voltage, and power
  - Battery voltage
  - Charging mode and status
  - Output current

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

## Usage

After installation and configuration, the integration will automatically create sensor entities for each detected inverter and charge controller. These sensors will update in real-time as new data is received from the MATE3 controller.

## Troubleshooting

If you're not seeing any data:

1. Verify that your MATE3 is configured to stream data to the correct IP address and port
2. Check your firewall settings to ensure UDP traffic is allowed on the configured port
3. Check the Home Assistant logs for any error messages

## Support

For issues and feature requests, please open an issue on the GitHub repository.
