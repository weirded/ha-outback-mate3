# Outback MATE3

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-orange?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/weirded)

Streams live data from your Outback MATE3 into Home Assistant. Listens for the MATE3's UDP telemetry on the LAN, polls its `/CONFIG.xml` every 5 minutes for firmware + setpoints, and ships a bundled companion integration into `/config/custom_components/outback_mate3/` on first start. You only install this add-on — the integration lands automatically.

## First run

1. Click **Install**, then **Start**. The defaults work.
2. On the MATE3 display: **LOCK** → code **141** → Settings → System → Data Stream. Set **Network Data Stream: Enabled**, **Destination IP** to your HA host, **Destination Port** to `57027`.
3. **Restart Home Assistant** once. The companion integration deployed by the add-on's first start only loads after a restart.
4. **Settings → Devices & Services** will show a **Discovered: Outback MATE3** card. Click **Submit**.

You should see ~90 live sensors per MATE3 install (system device + each inverter + each charge controller) plus another ~300 diagnostic sensors from the config poll, hidden by default. Enable the diagnostic ones you want from the device page.

## Options

| Option | Default | Description |
|---|---|---|
| `udp_port` | `57027` | UDP port the MATE3 streams to. Must match the MATE3's **Destination Port**. |
| `ws_port` | `8099` | TCP port the add-on exposes for the integration's WebSocket connection. |
| `log_level` | `info` | One of `trace`, `debug`, `info`, `notice`, `warning`, `error`, `fatal`. Bump to `debug` to log every datagram + every config-poll diff. |
| `min_update_interval_s` | `30` | Per-MAC throttle. Frames arriving within this window after the last accepted one are dropped. |
| `config_poll_interval_s` | `300` | How often (in seconds) to pull `http://<mate3>/CONFIG.xml`. `0` disables the poll entirely. |

## Troubleshooting

- **No devices appear in HA** — check the add-on log. You should see `First UDP datagram from <ip>` within seconds of starting. If not, verify the MATE3's Destination IP / Port on the MATE3 display and (per a known MATE3 firmware quirk) **power-cycle the MATE3** after changing its Data Stream destination — some firmware versions only pick up the new target on a full reboot.
- **Integration shows "cannot connect"** — make sure the add-on is running and the integration's WS URL points at `ws://local-outback-mate3:<ws_port>/ws` (the default). Supervisor resolves that hostname inside the HA core container.
- **Bundled integration not deployed** — the log will say `/homeassistant is not mapped — integration auto-deploy skipped` if the `homeassistant_config:rw` map is missing. Shouldn't happen on a stock install of this add-on; if you see it, check `config.yaml` has the `map:` block.
- **SD-card errors in the MATE3 log don't block the integration.** Config comes from the HTTP endpoint, not the card. Replace the card at your leisure.

## Support

Bugs and feature requests: [open a GitHub issue](https://github.com/weirded/ha-outback-mate3/issues).

If this add-on saved you a weekend:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-orange?logo=buy-me-a-coffee&logoColor=white)](https://buymeacoffee.com/weirded)
