# Outback MATE3 — Home Assistant Add-on Design

**Date:** 2026-04-17 (original design), last refreshed 2026-04-18 after the 2.0.0 ship
**Status:** Implemented and shipped as part of 2.0.0. Protocol, ports, and repository layout below reflect the code as of 2.0.0, not the original proposal. Material differences from the proposal are flagged inline.
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
┌────────────────┐       UDP :57027       ┌──────────────────────────────┐       WebSocket :28099       ┌──────────────────────┐
│   MATE3 unit   │ ─────────────────────▶ │   outback_mate3 add-on       │ ───────────────────────────▶ │  HA Core integration │
│  (on the LAN)  │         HTTP :80       │                              │   events:                    │  (custom component)  │
└────────────────┘ ◀───────────────────── │  - UDP listener              │    - snapshot                │                      │
                   CONFIG.xml pulled       │  - CONFIG.xml poller (5min) │    - device_added            │  - reacts to events  │
                   every 5 min             │  - MATE3 UDP parser         │    - state_updated           │  - creates HA        │
                                          │  - device + config registry  │    - config_snapshot         │    devices/entities  │
                                          │  - bundled integration       │                              │                      │
                                          │    auto-deploy               │                              │                      │
                                          └──────────────────────────────┘                              └──────────────────────┘
```

Responsibilities:

| Concern | Owner |
|---|---|
| Bind UDP, receive MATE3 packets | **Add-on** |
| Parse MATE3 UDP frames into device structures | **Add-on** |
| Poll MATE3's `CONFIG.xml` over HTTP; surface nameplate + setpoints | **Add-on** |
| Maintain in-memory registry of known devices and their current state | **Add-on** |
| Emit typed events on state change | **Add-on** |
| Announce to Supervisor for Hass.io auto-discovery | **Add-on** |
| Deploy bundled integration into `/config/custom_components/…` on start | **Add-on** |
| Connect to add-on over WebSocket | Integration |
| Create HA devices + entities from `snapshot` / `device_added` | Integration |
| Push state onto entities on `state_updated` events | Integration |
| Compute system-level aggregates (grid/solar/battery totals) on demand from per-device state | Integration |
| Materialize config-derived diagnostic sensors on first `config_snapshot` | Integration |
| Entity classes, units, `device_class`, `state_class` | Integration |
| Config flow, config entry, HA restart recovery | Integration |

The integration never parses a MATE3 byte. The add-on never knows what a Home Assistant entity is. The WebSocket protocol is the interface.

> **Changed from proposal:** the proposal placed aggregate computation in the add-on and emitted an `aggregates_updated` event. During implementation we realized the integration's existing `sensor.py` already computed totals on demand from per-device state, and the `combined_metrics` dict it computed into was dead code. Aggregates now live entirely on the integration side; there is no `aggregates_updated` event.

## Protocol (WebSocket at `/ws`)

JSON text frames. Message envelope: `{"type": "...", ...}`. WS port defaults to **28099** (moved from the originally-proposed 8099 because that port collides with other common HA add-ons).

**On client connect, server sends a snapshot of the currently-known devices, followed by the last-known config snapshot for each MAC that has been polled:**
```json
{
  "type": "snapshot",
  "devices": [
    {
      "mac": "001A2B-000001",
      "kind": "inverter",
      "index": 1,
      "state": { "l1_grid_power": 123.4, "l2_grid_power": 98.7, "...": "..." }
    },
    {
      "mac": "001A2B-000001",
      "kind": "charge_controller",
      "index": 1,
      "state": { "pv_current": 4.2, "pv_voltage": 80.1, "...": "..." }
    }
  ]
}
```
Immediately after, the server sends one `config_snapshot` per known MAC (if any config polls have succeeded), so the new client has the full picture without having to wait up to `config_poll_interval_s` for the next poll:
```json
{ "type": "config_snapshot", "mac": "001A2B-000001", "config": { "system": { ... }, "inverters": [ ... ], "charge_controllers": [ ... ], "mate3": { "firmware": "001.004.007", ... } } }
```

**On new device seen in a UDP frame:**
```json
{ "type": "device_added", "mac": "...", "kind": "inverter", "index": 2, "state": { ... } }
```

**On any state change (throttled to ≤1 per 30s per MAC by default — `min_update_interval_s`):**
```json
{ "type": "state_updated", "mac": "...", "kind": "inverter", "index": 1, "state": { ... } }
```

**On each successful MATE3 CONFIG.xml poll that changed:**
```json
{ "type": "config_snapshot", "mac": "...", "config": { ... } }
```
Polls that re-fetch unchanged config do **not** emit an event; the registry only broadcasts on diff.

**Keepalive:** handled at the aiohttp protocol level via the `heartbeat` parameter on both ends (30 s ping interval, automatic reconnect on timeout). No hand-rolled ping/pong JSON frames.

> **Changed from proposal:** originally we specced an `aggregates` block inside `snapshot` plus an `aggregates_updated` event and hand-rolled JSON ping/pong. Aggregates moved to the integration (see above); ping/pong was replaced by aiohttp's built-in heartbeat to avoid reinventing what the library already provides.

Design notes:
- Full `state` is sent every update (not deltas). Simpler, and payloads are small (<2 KB).
- `mac`, `kind`, `index` together identify a device — same as the pre-2.0 integration's `device_key`.
- `config_snapshot` stores the CONFIG.xml-derived nameplate + setpoints on `OutbackMate3.config_by_mac[mac]`; the integration materializes config-derived diagnostic sensors on the first successful snapshot per MAC (so MATE3s whose HTTP endpoint is unreachable don't leave phantom "unavailable" entities).
- No auth. Add-on is on the internal Docker/host network.
- Inside the add-on, UDP + config-poll events are funneled through a bounded `asyncio.Queue` drained by one broadcaster consumer task, then fanned out to connected clients in parallel with a per-client send timeout so one slow client can't stall the others.

## Repository Layout

```
/
├── custom_components/outback_mate3/      # thin WS client of the add-on
│   ├── __init__.py                       # OutbackMate3 coordinator; WS client loop
│   ├── config_flow.py                    # async_step_hassio + user-URL fallback
│   ├── sensor.py                         # live UDP entities + config-derived diagnostics
│   ├── binary_sensor.py                  # Receiving-Data connectivity sensor
│   ├── manifest.json                     # version (shared with add-on)
│   └── translations/
├── outback_mate3_addon/                  # HA add-on
│   ├── config.yaml                       # manifest, options, schema, hassio_api,
│   │                                     # discovery, map: [homeassistant_config:rw]
│   ├── translations/en.yaml              # Supervisor-UI option labels + port labels
│   ├── Dockerfile                        # BUILD_FROM multi-arch; bundles integration
│   ├── build.yaml                        # per-arch base-image map
│   ├── run.sh                            # bashio; deploys bundled integration on start
│   ├── requirements.txt                  # aiohttp
│   ├── bundled_integration/outback_mate3/ # synced copy of custom_components/outback_mate3/
│   └── src/
│       ├── main.py                       # entry point; wires pieces
│       ├── udp_listener.py               # asyncio DatagramProtocol → enqueue_broadcast
│       ├── parser.py                     # MATE3 UDP frame parser
│       ├── mate3_http.py                 # CONFIG.xml fetcher + XML parser
│       ├── config_poller.py              # periodic HTTP poll + change detection
│       ├── state.py                      # DeviceRegistry + throttle + config store
│       ├── ws_server.py                  # aiohttp WS; bounded queue + per-client isolation
│       └── discovery.py                  # Supervisor /discovery announce/withdraw
├── scripts/                              # dev harness (Proxmox HAOS VM automation)
├── repository.yaml                       # makes this repo installable as add-on repo
├── docs/
├── tests/                                # PHACC integration tests
├── TASKS.md
└── README.md
```

## Component Designs

### Add-on (`outback_mate3_addon/`)

**`config.yaml`** (HA add-on manifest):
- `slug: outback_mate3`, `name: "Outback MATE3"`, `version: "2.0.0"`
- `arch: [aarch64, amd64, armhf, armv7, i386]`
- `startup: services`, `boot: auto`
- `host_network: true` (so the MATE3 on the LAN can reach this container's UDP port)
- `init: false` (defer to the base image's s6-overlay; Docker's `tini` causes PID-1 conflicts)
- `hassio_api: true`, `discovery: [outback_mate3]` — lets the add-on announce itself for auto-discovery
- `map: [homeassistant_config:rw]` — lets `run.sh` drop the bundled integration into `/config/custom_components/outback_mate3/`
- `options: { udp_port: 57027, ws_port: 28099, log_level: "info", min_update_interval_s: 30, config_poll_interval_s: 300 }`
- `schema`: matching port/int/list validators

**`src/parser.py`:** pure function `parse_frame(bytes, remote_ip) -> list[DeviceUpdate]`. No HA imports. Device-block filter keys off the structural pattern `^\d+,\d+` so port IDs ≥ 10 aren't silently dropped.

**`src/state.py`:** holds `devices: dict[(mac, kind, index), dict]` and `configs: dict[mac, dict]`. `apply(updates) -> list[Event]` emits `DeviceAdded` / `StateUpdated`; `set_config(mac, config) -> changed: bool` stores the CONFIG.xml dict and returns whether it diverged from the previous. Per-MAC 30 s update throttle.

**`src/udp_listener.py`:** `asyncio.DatagramProtocol` on `0.0.0.0:$UDP_PORT`; on packet, call `parser.parse_frame` → `state.apply(...)` → `server.enqueue_broadcast(events)` (non-blocking, bounded).

**`src/mate3_http.py`:** `fetch_config(host, timeout)` pulls `http://<host>/CONFIG.xml` and returns a parsed dict of curated values (firmware versions, nameplate, setpoints across System / Inverters / Charge Controllers / AGS / Grid_Use). Returns `None` on unreachable hosts or malformed XML.

**`src/config_poller.py`:** after the first UDP datagram establishes the MATE3's IP, runs `fetch_config` every `$CONFIG_POLL_INTERVAL_S` (default 300) per known source. Enqueues a `ConfigSnapshot` event only when the parsed dict differs from the previous.

**`src/ws_server.py`:** aiohttp WebSocket at `/ws`. On connect, send `snapshot` + one `config_snapshot` per known MAC. Bounded `asyncio.Queue` buffers enqueued events; `run_broadcaster(stop)` consumer drains it and fans out to connected clients in parallel (each within a `_SEND_TIMEOUT_S` window, so a stuck client gets dropped rather than stalling peers). Heartbeat via aiohttp's `WebSocketResponse(heartbeat=30)`.

**`src/discovery.py`:** on add-on start, POSTs to `http://supervisor/discovery` with the add-on's hostname + WS port so HA surfaces a **Discovered: Outback MATE3** card. On shutdown, DELETEs the announcement. No-ops outside HA (when `SUPERVISOR_TOKEN` is unset).

**`src/main.py`:** reads env from `run.sh` (`UDP_PORT`, `WS_PORT`, `LOG_LEVEL`, `MIN_UPDATE_INTERVAL_S`, `CONFIG_POLL_INTERVAL_S`), wires listener → registry → server, spawns the config poller + broadcaster consumer tasks, announces discovery, installs SIGTERM handler.

**`run.sh`:** bashio-based. Exports options as env vars, copies `/opt/integration/outback_mate3/` (baked into the image by the Dockerfile) into `/homeassistant/custom_components/outback_mate3/` when it differs (avoids restart-spam on unchanged content), `exec python3 -m src.main`.

**`Dockerfile`:** `FROM $BUILD_FROM` (HA base image, Alpine-Python), `pip install -r requirements.txt`, copies `src/`, `run.sh`, and `bundled_integration/outback_mate3/` → `/opt/integration/outback_mate3/`.

### Integration (`custom_components/outback_mate3/`)

**`__init__.py`** is the WebSocket client:
- `OutbackMate3(DataUpdateCoordinator)`: opens `aiohttp.ClientSession.ws_connect(url, heartbeat=30)`, with exponential backoff reconnect (1 s → 30 s cap). Tracks `last_udp_at` for the connectivity binary sensor. Keyed-off-conditional logging so a stopped add-on doesn't produce a WARN every retry.
- On `snapshot`: reset per-MAC device caches, replay each device through the normal `create_device_entities` path.
- On `device_added`: materialize entities for the new (mac, kind, index) if not seen before.
- On `state_updated`: write into the per-MAC cache + `async_set_updated_data(None)` to refresh entities.
- On `config_snapshot`: store on `config_by_mac[mac]`; on the **first** such snapshot for a MAC, call `create_config_entities(…)` to materialize the CONFIG-derived diagnostic sensors (all `entity_registry_enabled_default=False` so they don't clutter the UI until a user opts in).
- On reconnect: keep `discovered_devices` so we don't re-announce entities HA already knows about.

**`config_flow.py`:**
- `async_step_user`: asks for a WS URL (default `ws://local-outback-mate3:28099/ws`). 5 s connectivity probe waits for `snapshot`.
- `async_step_hassio(HassioServiceInfo)`: auto-discovery from the add-on's announce. Uses `hassio_{slug}` as the unique ID and passes `updates={CONF_URL: url}` to `_abort_if_unique_id_configured` so later re-announces with a changed URL automatically update the existing entry (that's how the 8099 → 28099 port move migrated silently).
- `async_migrate_entry`: upgrades legacy 1.x entries (drop `port`, insert default `url`).

**`sensor.py`:**
- Live-UDP entity classes: `OutbackSystemSensor`, `OutbackInverterSensor`, `OutbackChargeControllerSensor`. Power-aggregate sensors on the System device compute totals on demand from `inverters[mac]` / `charge_controllers[mac]`.
- Config-derived diagnostic entities: `OutbackConfigDiagnosticSensor` (disabled by default). Table-driven per System / Inverter / Charge Controller, ~400 in total, covering firmware, nameplate, charger setpoints, low/high battery cutoffs, grid-tie config, AC1/AC2 input config, stack mode, MPPT, AUX output, Relay, Diversion, PV Trigger, Nite Light, HVT, LGT, Grid Mode Schedules, full AGS block, and all three Grid_Use TOU profiles.

**`binary_sensor.py`:** `binary_sensor.mate3_system_receiving_data` (device_class `connectivity`). Reads `True` iff `coordinator.last_udp_at` is within 300 s. Two refresh paths: coordinator listener (catches off→on instantly) + 30 s `async_track_time_interval` (catches on→off when the UDP stream goes silent).

**`manifest.json`:** version pinned to the shared release version, `iot_class: "local_push"`, `hassio: true`, `config_flow: true`, `requirements: []` (aiohttp comes from HA core).

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

Breaking change for existing users (all of whom were on Supervised per the pre-2.0 README warning). The 2.0.0 release notes document:
1. Install the add-on from the repo URL (Supervisor → Add-on Store → Repositories → `https://github.com/weirded/ha-outback-mate3`).
2. The add-on auto-deploys the matching integration to `/config/custom_components/outback_mate3/` on first start; restart HA once so it loads.
3. A **Discovered: Outback MATE3** card appears under **Settings → Devices & Services**; one click to add.
4. Legacy 1.x config entries migrate automatically via `async_migrate_entry` (drops the UDP-port field, inserts the default WS URL; user can edit if the add-on hostname differs).
5. MATE3's UDP destination setting is unchanged (still points to the HA host IP:57027).

Old UDP-direct code path is removed. HACS support is removed — the integration now ships bundled with the add-on, so users install one thing.

## Out of Scope

- MQTT Discovery (explicitly ruled out)
- Ingress UI for the add-on (no UI needed)
- Add-on authentication (local network only)
- Publishing the add-on to the official HA add-on store (community store / repo URL is enough for now)
- Moving the integration into HA core (stays bundled with the add-on)
