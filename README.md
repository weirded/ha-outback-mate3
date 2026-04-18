# Outback MATE3 for Home Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-orange?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/weirded)

**Monitor your Outback MATE3 power system in Home Assistant.** Per-inverter and per-charge-controller live power, voltages, currents, and modes on the Energy Dashboard, plus every setpoint from the MATE3's own settings screens as diagnostic sensors.

## Is this for you?

If you have an **Outback Power MATE3 system controller** (anything the MATE3 can monitor — Radian, FX/FXE/GS/GSE inverters, FLEXmax 60/80/Extreme charge controllers, FlexNet DC battery monitor) and you run **Home Assistant OS or Supervised**, this add-on + bundled integration surfaces every signal the MATE3 broadcasts and every parameter it exposes, without you babysitting anything.

If you're on HA Container or HA Core, use at your own risk — the add-on needs Supervisor, though the integration alone works if you can get the UDP listener running somewhere else.

## What it gives you

- **Live per-device metrics on the Energy Dashboard.** From Grid / Solar Production / From Battery / To Loads + Battery Voltage as system aggregates; per-leg (L1/L2) current, voltage, power for every inverter; PV current/voltage/power + output current/power for every charge controller.
- **Every inverter mode, AC mode, grid mode, and charge controller mode** as enum sensors you can put on cards or trigger automations on.
- **~400 diagnostic sensors** covering the MATE3's entire configuration surface — firmware versions on every component, nameplate (system type, nominal V, battery Ah, PV W, max inverter/charger/gen kW), every charger setpoint (Absorb/Float/EQ/Re-Bulk/Re-Float voltages + times), low/high battery cutoffs, grid-tie config, AC1/AC2 input config, stack mode, MPPT settings, RTS, AUX output / Relay / Diversion / PV Trigger / Nite Light, HVT / LGT / Grid Mode Schedules / Grid Use TOU / AGS block. All disabled-by-default; enable the ones you care about from the device page in HA.
- **Hass.io auto-discovery.** The add-on announces itself the moment it starts streaming; HA surfaces a **Discovered: Outback MATE3** card under **Devices & Services**. One click to add.
- **SD-card-independent.** Reads config from the MATE3's built-in web server (`/CONFIG.xml`) rather than the SD card, so it keeps working when the card flakes out (which mine did — this was the whole reason for the 2.0 rewrite).

## How it works

Two moving parts:

```
                ┌───────────────────────┐
                │  Outback MATE3        │
                │  (on your LAN, udp    │
                │   broadcast @ 57027,  │
                │   http @ 80)          │
                └───────────┬───────────┘
                            │  UDP stream (live) + HTTP poll (config)
                            ▼
    Home Assistant OS / Supervised
  ┌────────────────────────────────────┐
  │  outback_mate3 add-on              │
  │    - binds UDP 57027 (host_net)    │
  │    - parses MATE3 frames           │
  │    - polls CONFIG.xml every 5 min  │
  │    - WebSocket @ :8099/ws          │◄── integration connects here
  │    - ships companion integration   │
  │      into /config on startup       │
  └────────────────────────────────────┘
```

1. **The add-on** runs inside Home Assistant. It owns the UDP socket (HA Core can't bind UDP reliably on HAOS), parses MATE3 frames, polls the MATE3's `CONFIG.xml` every 5 min for firmware + setpoints, and exposes a structured WebSocket stream.
2. **The bundled integration** is a thin aiohttp WebSocket client subclassing `DataUpdateCoordinator` that creates the HA devices + sensors and mirrors the add-on's state. The add-on drops it into `/config/custom_components/outback_mate3/` on first start so you don't have to install two things.

## Installation

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fweirded%2Fha-outback-mate3)

Or manually:

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add `https://github.com/weirded/ha-outback-mate3`. Reload.
2. Find **Outback MATE3** in the store and click **Install**.
3. Click **Start**. Default options (UDP 57027, WS 8099, config poll 300 s) work out of the box.
4. **Restart Home Assistant** so the bundled integration loads — the add-on will have dropped it into `/config/custom_components/outback_mate3/` on first start.
5. A **Discovered: Outback MATE3** card appears under **Settings → Devices & Services**. Click **Submit**. Done.

Upgrading the add-on in the future pulls a fresh bundled integration automatically; the next HA restart loads it.

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

1. If you previously installed 1.x via HACS, remove it from HACS first so it doesn't fight with the bundled 2.x copy.
2. Install the 2.x add-on as above. It drops the 2.x integration into `/config/custom_components/outback_mate3/` on first start.
3. Restart Home Assistant. Your existing config entry migrates automatically. If the default add-on URL doesn't resolve on your setup, edit the integration's configuration to set the correct WebSocket URL.
4. Entity unique IDs are preserved, so existing dashboards, automations, and Energy Dashboard configuration continue to work.

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

## License

MIT — see [`LICENSE`](LICENSE).

## Support

Bugs and feature requests: [open a GitHub issue](https://github.com/weirded/ha-outback-mate3/issues).

If this saved you a weekend of yak-shaving, consider buying me a coffee:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-orange?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/weirded)
