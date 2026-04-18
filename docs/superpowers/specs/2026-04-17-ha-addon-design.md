# Outback MATE3 — Home Assistant Add-on Design

**Date:** 2026-04-17
**Status:** Proposed (revision 2 — structured WebSocket protocol)
**Scope:** Split the project into (a) a Home Assistant add-on that does all UDP I/O and MATE3 parsing and owns device state, and (b) a slimmed custom integration that connects to the add-on over WebSocket and creates/updates HA entities in response to typed events. The result works on Home Assistant OS.

## Context

The current project is a Home Assistant custom integration (`custom_components/outback_mate3`) that binds a UDP listener on port `57027` inside the HA Core container and creates sensor entities directly from parsed MATE3 packets. The README warns it does **not** work on Home Assistant OS — only on Supervised installs — because HA OS runs Core in a container where arbitrary UDP binding is unreliable.

We want the project to work on HA OS **without** an MQTT broker dependency. We also want the add-on to own device discovery and state, so the integration becomes a thin, reactive client rather than the source of truth.

## Prior art (this is a well-worn pattern)

Three in-tree HA add-on/integration pairs use the same shape we're adopting:

- **Z-Wave JS** — `zwave-js-server` (add-on) exposes a WebSocket; `homeassistant/components/zwave_js` connects as a client, receives a full node tree on `start_listening`, and creates entities from a hard-coded discovery schema ([repo](https://github.com/zwave-js/zwave-js-server), [python client](https://github.com/home-assistant-libs/zwave-js-server-python)).
- **Matter Server** — `python-matter-server` (add-on) exposes a WebSocket; `homeassistant/components/matter` maps clusters→entities via a discovery schema.
- **Music Assistant** — MA server (add-on) exposes a WebSocket; `homeassistant/components/music_assistant` uses the `music-assistant-client` library to mirror state.

In all three: **the add-on owns protocol state and emits typed events; the integration owns the HA-side entity schema.** No one in the HA ecosystem ships a "generic thin client" — MQTT Discovery is the only pattern that pushes entity schema out of the integration, and we're deliberately avoiding MQTT.

Our design follows this shape. Our "protocol" is smaller than Z-Wave's, but the division of responsibilities is the same.

## Chosen Architecture

```
┌────────────────┐       UDP :57027       ┌──────────────────────────────┐      WebSocket :8099        ┌──────────────────────┐
│   MATE3 unit   │ ─────────────────────▶ │   outback_mate3 add-on       │ ──────────────────────────▶ │  HA Core integration │
│  (on the LAN)  │                        │                              │                             │  (custom component)  │
└────────────────┘                        │  - UDP listener              │  events:                    │                      │
                                          │  - MATE3 parser              │    - snapshot               │  - reacts to events  │
                                          │  - device state registry     │    - device_added           │  - creates HA        │
                                          │  - WS server, fan-out        │    - state_updated          │    devices/entities  │
                                          └──────────────────────────────┘                             └──────────────────────┘
```

Responsibilities:

| Concern | Owner |
|---|---|
| Bind UDP, receive MATE3 packets | **Add-on** |
| Parse MATE3 frames into device structures | **Add-on** |
| Maintain in-memory registry of known devices and their current state | **Add-on** |
| Compute system-level aggregates (grid/solar/battery totals) | **Add-on** |
| Emit typed events on state change | **Add-on** |
| Connect to add-on over WebSocket | Integration |
| Create HA devices + entities from `device_added` events | Integration |
| Push state onto entities on `state_updated` events | Integration |
| Entity classes, units, `device_class`, `state_class` | Integration |
| Config flow, config entry, HACS packaging | Integration |

The integration never parses a MATE3 byte. The add-on never knows what a Home Assistant entity is. The WebSocket protocol is the interface.

## Protocol (WebSocket at `/ws`)

JSON text frames. Message envelope: `{"type": "...", ...}`.

**On client connect, server sends a snapshot of current state:**
```json
{
  "type": "snapshot",
  "devices": [
    {
      "mac": "001A2B-000001",
      "kind": "inverter",
      "index": 1,
      "state": { "l1_grid_power": 123.4, "l2_grid_power": 98.7, /* ... */ }
    },
    {
      "mac": "001A2B-000001",
      "kind": "charge_controller",
      "index": 1,
      "state": { "pv_current": 4.2, "pv_voltage": 80.1, /* ... */ }
    }
  ],
  "aggregates": {
    "001A2B-000001": { "total_grid_power": 222.1, /* ... */ }
  }
}
```

**On new device seen in a UDP frame:**
```json
{ "type": "device_added", "mac": "...", "kind": "inverter", "index": 2, "state": { ... } }
```

**On any state change (throttled to ≤1 per 30s per MAC, matching current behavior):**
```json
{ "type": "state_updated", "mac": "...", "kind": "inverter", "index": 1, "state": { ... } }
```

**On per-MAC aggregate change:**
```json
{ "type": "aggregates_updated", "mac": "...", "aggregates": { ... } }
```

**Keepalive:** server sends `{"type": "ping"}` every 30s; client replies `{"type": "pong"}`. Missing two pings in a row → client reconnects.

Design notes:
- Full `state` is sent every update (not deltas). Simpler, and payloads are small (<2KB).
- `mac`, `kind`, `index` together identify a device — same as the current integration's `device_key`.
- No auth. Add-on is on the internal Docker/host network.

## Repository Layout

```
/
├── custom_components/outback_mate3/      # existing; becomes a thin WS client
│   ├── __init__.py                       # connects to add-on, dispatches events to entity layer
│   ├── config_flow.py                    # asks for WS URL (instead of UDP port)
│   ├── sensor.py                         # entity classes (mostly unchanged structure)
│   ├── manifest.json                     # version bump, breaking change
│   └── translations/
├── outback_mate3_addon/                  # NEW add-on
│   ├── config.yaml                       # HA add-on manifest
│   ├── Dockerfile
│   ├── run.sh
│   ├── requirements.txt                  # aiohttp
│   └── src/
│       ├── main.py                       # entry point; wires pieces
│       ├── udp_listener.py               # asyncio DatagramProtocol
│       ├── parser.py                     # MATE3 frame parser (moved from custom_components/__init__.py)
│       ├── state.py                      # in-memory device registry + aggregate computation
│       └── ws_server.py                  # aiohttp WS with snapshot + event stream
├── repository.yaml                       # NEW — makes this repo installable as add-on repo
├── docs/
├── TASKS.md
└── README.md
```

## Component Designs

### Add-on (`outback_mate3_addon/`)

**`config.yaml`** (HA add-on manifest):
- `slug: outback_mate3`, `name: "Outback MATE3"`, `version: "0.1.0"`
- `arch: [aarch64, amd64, armhf, armv7, i386]`
- `startup: services`, `boot: auto`
- `host_network: true` (so the MATE3 on the LAN can reach this container's UDP port)
- `options: { udp_port: 57027, ws_port: 8099, log_level: "info", min_update_interval_s: 30 }`
- `schema`: matching port/int/list validators

**`src/parser.py`:** pure function `parse_frame(bytes, remote_ip) -> list[DeviceUpdate]`. Lifted from `custom_components/outback_mate3/__init__.py` (methods `_process_data`, `_process_device`, `_process_inverter`, `_process_charge_controller`). No HA imports.

**`src/state.py`:** holds `devices: dict[(mac, kind, index), dict]` and per-MAC `aggregates: dict[mac, dict]`. Apply a `DeviceUpdate`, returns a change set (new devices and/or state diffs) for the server to emit. Computes aggregates the same way the current `_process_data()` does (total grid/inverter/charger power, averaged voltages).

**`src/udp_listener.py`:** `asyncio.DatagramProtocol` on `0.0.0.0:$UDP_PORT`; on packet, call `parser.parse_frame` → `state.apply(...)` → `server.broadcast(events)`.

**`src/ws_server.py`:** aiohttp WebSocket at `/ws`. On connect, send `snapshot`. Maintain `set[WebSocketResponse]`; `broadcast(event)` sends to all, drops dead clients. Ping/pong every 30s.

**`src/main.py`:** reads env from `run.sh` (`UDP_PORT`, `WS_PORT`, `LOG_LEVEL`, `MIN_UPDATE_INTERVAL_S`), wires listener → state → server, installs SIGTERM handler.

**`run.sh`:** bashio-based, exports options as env vars, `exec python3 /app/main.py`.

**`Dockerfile`:** `FROM $BUILD_FROM` (HA base image, Alpine-Python), `pip install -r requirements.txt`, copies `src/` and `run.sh`.

### Integration (`custom_components/outback_mate3/`)

**`__init__.py`** becomes a WebSocket client:
- `OutbackMate3Client` (replaces `OutbackMate3`): opens `aiohttp.ClientSession.ws_connect(url)`, with exponential backoff reconnect (1s → 30s cap).
- On `snapshot`: for each device in the payload, call entity-creation path; update aggregates.
- On `device_added`: call entity-creation path for that device.
- On `state_updated` / `aggregates_updated`: stash state and call `async_set_updated_data(None)` so coordinator consumers refresh.
- On reconnect: discard any existing device/aggregate state and re-create from the new `snapshot` (devices are idempotent by `(mac, kind, index)`).
- On disconnect past N seconds: mark all entities unavailable.

**`config_flow.py`:**
- Replace `CONF_PORT` with `CONF_URL` (e.g. `ws://a0d7b954-outback-mate3:8099/ws`).
- Connectivity probe: open WS with 5s timeout; wait for `snapshot`; abort on failure.
- `async_migrate_entry` upgrades old entries (drops `port`, inserts default `url`, user can edit).

**`sensor.py`:**
- Entity classes stay. `create_device_entities()` already takes the coordinator + MAC and materializes the right set — we keep calling it from the new event handlers.
- The inner dicts `inverters[mac][no]` and `charge_controllers[mac][no]` are populated by WS events instead of by local parsing. Property accessors on entities keep reading from those dicts, so entity code is unchanged.

**`manifest.json`:** version bump to `2.0.0`, still `iot_class: "local_push"`, `requirements: []` (aiohttp comes from HA core).

## Error Handling

**Add-on:**
- Malformed UDP frame → log at debug, discard, continue.
- UDP socket error → log + process exits nonzero (Supervisor restarts).
- WebSocket send error to a client → drop that client only.

**Integration:**
- Connect failure → backoff 1s, 2s, 4s, …, cap 30s, forever.
- Disconnected longer than 60s → entities go `unavailable`.
- Unknown event `type` → log at warning, ignore; forward-compatible with newer add-on versions.

## Testing

- **Add-on unit tests:** `pytest` against `parser.py` and `state.py` using captured MATE3 frames (fixtures from a real unit).
- **Add-on integration test:** spin up `main.py` locally, `nc -u` a real frame in, `wscat` to `/ws`, assert `snapshot` + `state_updated` sequence.
- **Integration tests:** `pytest-homeassistant-custom-component`. Fixture: a local aiohttp WS server that plays a canned event stream. Assertions: expected entities are created with expected attributes; state matches after each `state_updated`.
- **End-to-end:** install add-on and integration on a real HA OS box, point a real MATE3 at the HA host, verify sensors populate and track live changes.

## Migration

Breaking change for existing users (all of whom are on Supervised per the README warning). Release notes document:
1. Install the add-on from the repo URL.
2. Re-add the integration; config flow now asks for WS URL.
3. MATE3's UDP destination setting is unchanged (still points to the HA host IP:57027).

Old UDP-direct code path is removed.

## Out of Scope

- MQTT Discovery (explicitly ruled out)
- Ingress UI for the add-on (no UI needed)
- Add-on authentication (local network only)
- Publishing the add-on to the official HA add-on store (community store / repo URL is enough for now)
- Moving the integration into HA core (stays HACS-distributed)
