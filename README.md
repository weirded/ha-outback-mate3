# Home Assistant Outback MATE3 Integration

This custom component integrates the Outback MATE3 system controller with Home Assistant, providing real-time monitoring of Outback power system components including inverters and charge controllers.

## Features

- Real-time monitoring of Outback MATE3 devices via UDP
- Support for multiple inverters and charge controllers
- Energy monitoring compatible with Home Assistant's Energy Dashboard
- System-wide power and energy metrics

## Installation

1. Copy the `custom_components/outback_mate3` directory to your Home Assistant configuration directory
2. Restart Home Assistant
3. Add the integration through the Home Assistant UI (Settings -> Devices & Services -> Add Integration -> Outback MATE3)

## Available Sensors

### System Device
Combined metrics for your entire Outback system:
- From Grid (W) - Positive for consumption, negative for production
- Solar Production (W) - Always positive (production)
- From Battery (W) - Positive for discharge, negative for charge
- To Loads (W) - Total power to loads (From Grid + From Battery)
- Battery Voltage (V) - System battery voltage
- Solar Production Energy (kWh) - Daily solar production

### Inverter Device
Per-inverter metrics:
- Current (A)
- Charger Current (A)
- Buy Current (A)
- Sell Current (A)
- AC Input Voltage (V)
- AC Output Voltage (V)
- Battery Voltage (V)

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

## Configuration

The integration requires:
1. MATE3 IP address
2. UDP port (default: 57027)

For optimal performance, configure your MATE3 to:
1. Enable UDP notifications
2. Set the UDP port to match your configuration
3. Set an appropriate update frequency (recommended: 1 second)

## Troubleshooting

If you're not seeing data:
1. Verify MATE3 network connectivity
2. Check UDP port configuration
3. Ensure UDP notifications are enabled on MATE3
4. Check Home Assistant logs for any error messages

## Support

For bugs and feature requests, please open an issue on GitHub.
