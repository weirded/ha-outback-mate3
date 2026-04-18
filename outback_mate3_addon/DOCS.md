# Outback MATE3 add-on

Listens for Outback MATE3 UDP streaming telemetry and relays parsed device state to the companion [Outback MATE3 Home Assistant integration](../custom_components/outback_mate3) (or any other WebSocket client) as typed JSON events.

This add-on does not create Home Assistant entities by itself. It's a bridge between the LAN-facing UDP port and the HA-facing WebSocket consumed by the integration.

## Why an add-on?

On Home Assistant OS, the core container's networking makes it unreliable for arbitrary UDP listeners. Running the UDP socket in an add-on with `host_network: true` works consistently across HA OS, Supervised, and Container installs.

## Options

| Option | Default | Description |
|---|---|---|
| `udp_port` | `57027` | UDP port the MATE3 streams telemetry to. Must match the MATE3's `Destination Port`. |
| `ws_port` | `8099` | WebSocket port the add-on exposes on the host; the integration connects here. |
| `log_level` | `info` | One of `trace`, `debug`, `info`, `notice`, `warning`, `error`, `fatal`. |
| `min_update_interval_s` | `30` | Per-MAC throttle. Frames arriving more often than this are dropped. |

## MATE3 configuration

On the MATE3 display:

1. Press **LOCK**, enter user code **141**
2. Settings → System → **Data Stream**
3. Set **Network Data Stream** to **Enabled**
4. Set **Destination IP** to the IP of your Home Assistant host
5. Set **Destination Port** to `udp_port` (default `57027`)

## Troubleshooting

- **No devices appear in HA** — check the add-on's log. You should see connection logs for the integration. If you see nothing from the MATE3 at all, verify the MATE3's Destination IP / Port and that the MATE3 is actually streaming.
- **Integration shows "cannot connect"** — make sure the add-on is running and the integration's configured URL points at the add-on's host and `ws_port`. Default is `ws://local-outback-mate3:8099/ws`.
