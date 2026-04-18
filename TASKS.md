# TASKS — Outback MATE3 Home Assistant Add-on (structured WS protocol)

Breakdown for splitting the project into:
- a **Home Assistant add-on** (`outback_mate3_addon/`) that owns UDP I/O, MATE3 parsing, device state, and a WebSocket server emitting typed events, and
- a **slim custom integration** (`custom_components/outback_mate3/`) that connects to the add-on over WebSocket and creates/updates HA entities in response to those events.

Design doc: [`docs/superpowers/specs/2026-04-17-ha-addon-design.md`](docs/superpowers/specs/2026-04-17-ha-addon-design.md)
Prior art this mirrors: Z-Wave JS, Matter Server, Music Assistant.

---

## Phase 1 — Capture MATE3 fixtures for testing

_Do this first: without real UDP packets on disk, every later phase is guesswork._

- [x] **1.1** On an existing working install (Supervised), capture a few minutes of raw MATE3 UDP packets to a file (`tcpdump -i any -w mate3.pcap udp port 57027` or a small Python script that writes each datagram as one line).
- [x] **1.2** Extract 5–10 representative frames into `tests/fixtures/mate3_frames/` (one file per frame, raw bytes). Include at least: inverter-only, charge-controller-only, and mixed frames.

## Phase 2 — Extract MATE3 parser into a standalone module

_Goal: a pure Python module with no HA imports that both the add-on will use and that can be unit-tested in isolation._

- [x] **2.1** Create `outback_mate3_addon/src/parser.py`. Port the parsing logic currently in `custom_components/outback_mate3/__init__.py` — methods `_process_data`, `_process_device`, `_process_inverter`, `_process_charge_controller` — as a pure function `parse_frame(data: bytes, remote_ip: str) -> list[DeviceUpdate]` where `DeviceUpdate` is a dataclass with `mac`, `kind` ("inverter" | "charge_controller"), `index`, `state` (dict of the parsed fields).
- [x] **2.2** Remove HA-specific concerns from the parser (no `_LOGGER` from HA, no coordinator refs — use stdlib `logging`).
- [x] **2.3** Write `outback_mate3_addon/tests/test_parser.py` covering every fixture captured in Phase 1; assert exact field values for the known-good frames.

## Phase 3 — Device state registry + aggregates

- [x] **3.1** Create `outback_mate3_addon/src/state.py` with a `DeviceRegistry` class holding `devices: dict[tuple[str,str,int], dict]` and `aggregates: dict[str, dict]`.
- [x] **3.2** Implement `apply(updates: list[DeviceUpdate]) -> list[Event]` where `Event` is `DeviceAdded | StateUpdated`. ~~Aggregates~~ — dropped after discovering that the integration's `combined_metrics` was dead code (`sensor.py` computes totals on demand from per-device state).
- [x] **3.3** Enforce the existing 30-second per-MAC throttle (`min_update_interval_s` option) inside the registry.
- [x] **3.4** Unit tests in `outback_mate3_addon/tests/test_state.py` — feed fixture-parsed `DeviceUpdate`s, assert event sequence and aggregate correctness.

## Phase 4 — Add-on WebSocket server

- [x] **4.1** Create `outback_mate3_addon/src/ws_server.py` — aiohttp app with one route `/ws`. On connect, send `{"type": "snapshot", "devices": [...], "aggregates": {...}}` built from the `DeviceRegistry`'s current state.
- [x] **4.2** Maintain a `set[WebSocketResponse]`; `broadcast(event: dict)` sends to all, catches send errors, prunes dead clients.
- [x] **4.3** ~~Hand-rolled ping/pong~~ — delegated to aiohttp's protocol-level `heartbeat=30` parameter on both ends.
- [x] **4.4** Unit test using `aiohttp.test_utils` — open a client WS, assert snapshot shape, inject events via `broadcast()`, assert client receives them.

## Phase 5 — Add-on wiring and container scaffolding

- [x] **5.1** Create `outback_mate3_addon/src/udp_listener.py` — `asyncio.DatagramProtocol` on `0.0.0.0:$UDP_PORT`; on each datagram, call `parser.parse_frame → registry.apply → server.broadcast(events)`.
- [x] **5.2** Create `outback_mate3_addon/src/main.py` — parse env, create loop, start UDP listener + aiohttp server, install SIGTERM handler for graceful shutdown, log startup banner.
- [x] **5.3** Create `outback_mate3_addon/config.yaml` with `slug`, `name`, `version: 0.1.0`, `arch`, `startup: services`, `boot: auto`, `host_network: true`, `options` (`udp_port: 57027`, `ws_port: 8099`, `log_level: info`, `min_update_interval_s: 30`), matching `schema`.
- [x] **5.4** Create `outback_mate3_addon/Dockerfile`: `ARG BUILD_FROM`, `FROM $BUILD_FROM`, install python+pip, copy `src/` + `requirements.txt`, `pip install -r requirements.txt`, copy `run.sh`, `CMD ["/run.sh"]`.
- [x] **5.5** Create `outback_mate3_addon/run.sh` — `#!/usr/bin/with-contenv bashio`, read options via `bashio::config`, export env vars, `exec python3 /app/main.py`.
- [x] **5.6** Create `outback_mate3_addon/requirements.txt` (`aiohttp`).
- [x] **5.7** Create `repository.yaml` at repo root so Supervisor can add this repo as an add-on repository.

## Phase 6 — Local add-on end-to-end sanity check

- [ ] **6.1** `docker build` the add-on image locally.
- [ ] **6.2** `docker run --network=host -e UDP_PORT=57027 -e WS_PORT=8099 <image>` — verify it starts.
- [ ] **6.3** With a Python script, send a captured MATE3 fixture datagram over UDP.
- [ ] **6.4** Connect with `wscat -c ws://localhost:8099/ws` and confirm the snapshot and subsequent `device_added` / `state_updated` events arrive correctly.

## Phase 7 — Integration: rewrite as WS client

- [x] **7.1** In `custom_components/outback_mate3/__init__.py`, replace `OutbackMate3` (the parser + coordinator) with `OutbackMate3Client` — an `aiohttp`-based WebSocket client subclassing `DataUpdateCoordinator`.
- [x] **7.2** Implement connect + reconnect with exponential backoff (1s → 30s cap) in an `asyncio.Task`.
- [x] **7.3** On `snapshot`: reset local caches (`self.inverters`, `self.charge_controllers`, `self.combined_metrics`), then for each device call the same `create_device_entities(self, mac)` path already used today.
- [x] **7.4** On `device_added`: update caches; call `create_device_entities` if this is a new MAC/kind/index combination (keep the existing `discovered_devices` set).
- [x] **7.5** On `state_updated` and `aggregates_updated`: write into caches, call `self.async_set_updated_data(None)` to refresh entities.
- [x] **7.6** Delete all UDP/socket code from `__init__.py` and all MATE3 parsing helpers (they now live in the add-on).

## Phase 8 — Integration: config flow + manifest

- [x] **8.1** In `custom_components/outback_mate3/config_flow.py`, replace `CONF_PORT` with `CONF_URL`; default to `ws://a0d7b954-outback-mate3:8099/ws` (verify actual slug-derived hostname on a real install).
- [x] **8.2** Add a connectivity probe: open the WS with a 5s timeout, wait for the `snapshot` frame; present a user-friendly error if it fails.
- [x] **8.3** Implement `async_migrate_entry` to map legacy entries (with `port`) to the new `url` form using the default.
- [x] **8.4** Bump `manifest.json` version (e.g. `2.0.0`); update `config_flow.py` `VERSION = 2`.
- [x] **8.5** Update translations under `custom_components/outback_mate3/translations/` for the new field label.

## Phase 9 — Integration tests

- [ ] **9.1** Set up `pytest-homeassistant-custom-component` in dev deps if not already configured.
- [ ] **9.2** Write a pytest fixture that boots a local aiohttp WS server which replays a canned event stream (the same shape the add-on emits).
- [ ] **9.3** Write a test that sets up the integration against the fixture, waits for entities to register, asserts the expected set of entities exist with the right unique IDs / device classes, and verifies state after a `state_updated` event.
- [ ] **9.4** Write a reconnect test: kill the WS mid-stream, assert entities go `unavailable`, bring it back, assert state recovers from the new `snapshot`.

## Phase 10 — Docs & release

- [x] **10.1** Update `README.md`: remove the "does not work on HA OS" warning, add sections explaining the two-part install (add-on from repo URL, integration from HACS), and add a breaking-change note for existing users.
- [x] **10.2** Add `outback_mate3_addon/README.md` explaining options, what to point MATE3 at (host IP:57027), and troubleshooting.
- [ ] **10.3** Check `hacs.json` — it tracks the integration, not the add-on; likely no change needed.
- [x] **10.4** Write release notes / CHANGELOG for the 2.0 cut.

## Phase 11 — End-to-end validation on real HA OS

- [ ] **11.1** Install the add-on on an HA OS instance by adding this repo's URL to Supervisor.
- [ ] **11.2** Install the integration via HACS on the same instance.
- [ ] **11.3** Configure MATE3 to stream to the HA host IP on port 57027.
- [ ] **11.4** Verify entities appear with correct values; cross-check against the MATE3 display (and, if available, a Supervised install running the old version).
- [ ] **11.5** Restart the add-on; confirm integration reconnects and entities recover.
- [ ] **11.6** Restart HA Core; confirm integration reconnects and entities recover.

## Phase 12 — Hass.io discovery (auto-suggest the add-on to the integration)

When the add-on is running, HA should automatically surface the integration under **Settings → Devices & Services → Discovered**, pre-filled with the add-on's WebSocket URL. No manual config flow needed.

- [x] **12.1** Add `hassio_api: true` and `discovery: [outback_mate3]` to `outback_mate3_addon/config.yaml`. The first grants the add-on permission to talk to Supervisor; the second declares which service names it may announce.
- [x] **12.2** Implement discovery announce in `outback_mate3_addon/src/main.py`. On startup, if `SUPERVISOR_TOKEN` is set, POST to `http://supervisor/discovery` with `{"service": "outback_mate3", "config": {"host": "<addon-hostname>", "port": <ws_port>}}`. Store the returned UUID. On graceful shutdown, DELETE `/discovery/{uuid}`. Failures log and continue — running outside HA (plain Docker) must still work.
- [x] **12.3** Set `"hassio": true` in `custom_components/outback_mate3/manifest.json` so HA routes Hass.io discovery events for our service name to this integration.
- [x] **12.4** Implement `async_step_hassio(discovery_info: HassioServiceInfo)` in `custom_components/outback_mate3/config_flow.py`. Build the WS URL from `discovery_info.config`, set a stable unique_id so repeated announces don't create duplicates (and update the URL if it changed), show a confirmation step.
- [x] **12.5** Add strings for the `hassio_confirm` step to `custom_components/outback_mate3/translations/en.json`.
- [x] **12.6** Verify end-to-end on the HAOS test VM: after `./scripts/install-addon.sh`, a "Discovered: Outback MATE3" notification appears in HA within a few seconds; clicking through auto-creates an entry with the correct WS URL.

## Phase 13 — Nice-to-haves (defer unless small and obvious)

- [ ] **13.1** Add `/healthz` HTTP endpoint to the add-on for Supervisor healthchecks.
- [ ] **13.2** Add optional simple token auth between integration and add-on (shared secret in add-on options, echoed in integration config).
- [ ] **13.3** Publish the add-on to a broader community add-on index.

## Bugfixes/Tweaks

_Each completed item is annotated with `(vX.Y.Z-devN)` — the add-on / integration version running on VM 106 when the fix was deployed. Used to derive the changelog._

- [x] B1 - we don't need to describe the WebSocket protocol on docs.md. _(2.0.0-dev1)_
- [x] B2 - we are missing a changelog; let's fix that.  _(2.0.0-dev1)_
- [x] B3 - the add-on is missing the icon that we had for the integration before. Let's fix that also. _(2.0.0-dev1)_
- [x] B4 - let's make the version of the add-on and integration match always. _(2.0.0-dev1)_
- [x] B5 - while we develop, let's append a .devN suffix to the version and increment N on each turn, so that I can see when we are running a newer version. _(2.0.0-dev1)_
- [x] B6 - after each turn, update TASKS.md, noting the specific version that fixed the task. We are going to use tasks.md to derive a changelog. _(2.0.0-dev1)_