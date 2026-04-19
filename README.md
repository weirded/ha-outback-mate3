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

Two moving parts live inside Home Assistant — the **add-on** (UDP listener + HTTP config poller + WebSocket server) and the **integration** (WebSocket client that creates HA devices and sensors). The add-on ships the integration on first run, so you only install the add-on:

```
   ┌───────────────────┐
   │  Outback MATE3    │
   │  on your LAN      │
   │  (UDP broadcast   │
   │   @ 57027,        │
   │   HTTP @ 80)      │
   └─────────┬─────────┘
             │ UDP live stream + HTTP config poll (every 5 min)
             ▼
   ════════════════════════════════════════════════════════════════════
   Home Assistant OS / Supervised
   ════════════════════════════════════════════════════════════════════
   ┌────────────────────────────────┐        ┌─────────────────────────┐
   │ outback_mate3 add-on           │        │ outback_mate3           │
   │  • binds UDP :57027 (host_net) │        │ integration             │
   │  • parses MATE3 frames         │  ws    │  • DataUpdateCoordinator│
   │  • polls CONFIG.xml            │◄──────►│  • creates HA devices + │
   │  • WebSocket server @ :28099   │:28099/ws│    sensors              │
   │  • ships integration into      │        │  • auto-discovered by HA│
   │    /config/custom_components/  │        │    on first add-on start│
   └────────────────────────────────┘        └────────────┬────────────┘
                                                          │
                                                          ▼
                                              Home Assistant UI, Energy
                                              Dashboard, automations
```

1. **The add-on** owns the UDP socket (HA Core can't bind UDP reliably on HAOS), parses MATE3 frames, polls the MATE3's `CONFIG.xml` every 5 min for firmware + setpoints, and exposes a structured WebSocket stream.
2. **The integration** is a thin aiohttp WebSocket client subclassing `DataUpdateCoordinator` that creates HA devices + sensors and mirrors the add-on's state. The add-on drops it into `/config/custom_components/outback_mate3/` on first start so you don't have to install two things; Home Assistant auto-discovers it via Hass.io discovery.

## Installation

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fweirded%2Fha-outback-mate3)

Or manually:

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add `https://github.com/weirded/ha-outback-mate3`. Reload.
2. Find **Outback MATE3** in the store and click **Install**.
3. Click **Start**. Default options (UDP 57027, WS 28099, config poll 300 s) work out of the box.
4. **Restart Home Assistant** so the bundled integration loads — the add-on will have dropped it into `/config/custom_components/outback_mate3/` on first start.
5. A **Discovered: Outback MATE3** card appears under **Settings → Devices & Services**. Click **Submit**. Done.

Upgrading the add-on in the future pulls a fresh bundled integration automatically; the next HA restart loads it.

## Configuration

### MATE3 Setup

The add-on uses the MATE3's UDP streaming protocol. Configure your MATE3 to send data to your Home Assistant host:

##### On your MATE3 display:

<img width="333" alt="image" src="https://github.com/user-attachments/assets/901fe6d2-e2d2-4d18-b52b-91fd214d74fe" />

- Press the LOCK button
- Enter the installer code. The factory default is **141**, but whoever commissioned your system may have changed it — use whatever code unlocks Settings at your site.
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

The integration creates three HA device types: one **Outback System** (aggregates), one **Outback Inverter** per inverter the MATE3 sees, and one **Outback Charge Controller** per charge controller. Live UDP-stream metrics below are enabled-by-default; CONFIG.xml-derived diagnostic sensors are all disabled-by-default — enable the handful you want from the device page in HA.

### Outback System (one per install)
Live aggregates computed from all inverters + charge controllers:
- **From Grid** (W), **Solar Production** (W), **From Battery** (W), **To Loads** (W) — all four signed (positive/negative encodes direction).
- **Battery Voltage** (V) — averaged from the charge controllers.
- **Solar Production Energy** (kWh, totalizing) — Energy-Dashboard ready.
- **MATE3 Connected** (binary) — flips to Off after 5 minutes without a UDP frame.

Diagnostic (disabled-by-default) from the CONFIG.xml poll: MATE3 firmware version; data-stream target (catches "saved but not applied"); SD-card log mode; system type / nominal V / battery Ah / PV W / max inverter kW / max charger kW / generator kW; Low-SOC warn/error; AC-coupled mode; global CC output cap; SunSpec/Modbus settings; FNDC integration; all three Grid Mode Schedules (enable, start, stop, mode); HVT (high-battery transfer) and LGT (load grid transfer) blocks; full Advanced Generator Start block (51 fields — enable mode, VDC/SOC/load/temp/exercise/quiet-time triggers, generator profile, run-limits, warm-up/cool-down, DC-gen absorb/float/bulk/EQ setpoints); and Grid_Use / Grid_Use_P2 / Grid_Use_P3 TOU schedules.

### Outback Inverter (one per inverter)
Live per-inverter (positive/negative values encode direction where applicable):
- **L1 / L2 / Total** for Inverter Current, Charger Current, Buy Current, Sell Current.
- **L1 / L2 / Total** for AC Input Voltage, AC Output Voltage.
- **L1 / L2 / Total** for Grid Power, Inverter Power, Charger Power.
- **Battery Voltage** (V).
- **Inverter Mode**, **AC Mode**, **Grid Mode** as enum sensors.

Diagnostic (disabled-by-default) from CONFIG.xml: firmware version, nameplate type, configured inverter mode, low/high battery cut-out/cut-in voltages + delays, AC output voltage, charger mode, absorb/float/EQ/re-bulk/re-float setpoints + times, grid-tie mode/voltage/window (IEEE/UL), AC1 and AC2 input priority/type/size/min/max voltage, stack mode.

### Outback Charge Controller (one per charge controller)
Live per-CC:
- PV Current (A), PV Voltage (V), PV Power (W).
- Output Current (A), Output Power (W), Battery Voltage (V).
- **Charge Mode** as an enum sensor.

Diagnostic (disabled-by-default) from CONFIG.xml: firmware, model type (FM/FM80/FMX/FlexMax Extreme), absorb/float/EQ/re-bulk setpoints + times + end-amps, output-limit cap, MPPT mode/sweep/max-sweep, grid-tie enable.

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

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for a symptom-driven
walkthrough of the common failure modes (discovery card missing,
`MATE3 Connected` off, Energy Dashboard skipping the sensors, repairs
issues, etc.) and [`docs/faq.md`](docs/faq.md) for common questions.

## Further reading

- [`docs/architecture.md`](docs/architecture.md) — why the integration is
  split into two halves, why WebSocket, the security model, and the
  single-version coupling.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — symptom → diagnosis
  walkthroughs.
- [`docs/faq.md`](docs/faq.md) — common questions.
- [`CHANGELOG.md`](CHANGELOG.md) — decision history + what shipped when.

## License

MIT — see [`LICENSE`](LICENSE).

## Support

Bugs and feature requests: [open a GitHub issue](https://github.com/weirded/ha-outback-mate3/issues).

If this saved you a weekend of yak-shaving, consider buying me a coffee:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-orange?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/weirded)
