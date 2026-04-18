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

- [x] **6.1** `docker build` the add-on image locally against `ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.19` — built cleanly; this surfaced the `bashio` "null" fallback + `pre-enrolled-keys` + missing `build.yaml` + `init: false` bugs now fixed. _(pre-2.0.0-dev1)_
- [x] **6.2** `docker run -d --name outback-mate3-smoke --network=host -e UDP_PORT=57127 -e WS_PORT=8199 ...` — boots clean, prints "Listening for MATE3 UDP", "WebSocket server listening". _(pre-2.0.0-dev1)_
- [x] **6.3** Python `socket.sendto(fixture, (127.0.0.1, 57127))` with `telemetry_00.bin` — payload picked up by the listener, parsed, broadcast. _(pre-2.0.0-dev1)_
- [x] **6.4** aiohttp WS client against `ws://127.0.0.1:8199/ws` — confirmed empty snapshot on connect, then 4 `device_added` events (2 inverters, 2 charge controllers) with correct `kind`/`index`. _(pre-2.0.0-dev1)_

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

- [x] **9.1** Set up `pytest-homeassistant-custom-component` in dev deps if not already configured. _(2.0.0-dev10)_
- [x] **9.2** Write a pytest fixture that boots a local aiohttp WS server which replays a canned event stream (the same shape the add-on emits). _(2.0.0-dev10)_
- [x] **9.3** Write a test that sets up the integration against the fixture, waits for entities to register, asserts the expected set of entities exist with the right unique IDs / device classes, and verifies state after a `state_updated` event. _(2.0.0-dev10)_
- [x] **9.4** Write a reconnect test: kill the WS mid-stream, assert entities go `unavailable`, bring it back, assert state recovers from the new `snapshot`. _(2.0.0-dev10)_

## Phase 10 — Docs & release

- [x] **10.1** Update `README.md`: remove the "does not work on HA OS" warning, add sections explaining the two-part install (add-on from repo URL, integration from HACS), and add a breaking-change note for existing users.
- [x] **10.2** Add `outback_mate3_addon/README.md` explaining options, what to point MATE3 at (host IP:57027), and troubleshooting.
- [x] **10.3** ~~Check `hacs.json`~~ → Dropped HACS entirely (`hacs.json` removed, README badges and install instructions updated, CHANGELOG notes the removal). _(2.0.0-dev4)_
- [x] **10.4** Write release notes / CHANGELOG for the 2.0 cut.

## Phase 11 — End-to-end validation on real HA OS

- [ ] **11.1** Install the add-on on an HA OS instance by adding this repo's URL to Supervisor. _(still pending — we've only validated sideload via `install-addon.sh`; the repo-URL store path is untested)_
- [ ] **11.2** Install the integration via HACS on the same instance. _(still pending — we've only validated sideload via `install-integration.sh`)_
- [x] **11.3** Configure MATE3 to stream to the HA host IP on port 57027. _(2.0.0-dev2, verified via tcpdump)_
- [x] **11.4** Verify entities appear with correct values; cross-check against the MATE3 display. _(2.0.0-dev10 — UDP-stream entities match live MATE3 values; every config-derived diagnostic sensor was spot-checked against `http://<mate3>/CONFIG.xml` and the Radian + CC settings screenshots from the MATE3 web UI: absorb V = 55.2/55.4, low-batt cut-out 48.0 V, AC1 input size 200.0 A, CC output limit 80.0 A, MPPT upick 77 %, AUX PV trigger 140.0 V, Nite Light threshold 10.0 V, HVT disconnect 52.0 V, etc. — all match.)_
- [x] **11.5** Restart the add-on; confirm integration reconnects and entities recover. _(2.0.0-dev3 — add-on restart this turn, integration reconnected, new snapshot applied)_
- [x] **11.6** Restart HA Core; confirm integration reconnects and entities recover. _(2.0.0-dev1 — every `install-integration.sh` run issues `ha core restart` and the integration re-binds the add-on WS cleanly)_

## Phase 14 — MATE3 HTTP config poll (nameplate, firmware, setpoints)

The UDP stream gives live readings. The MATE3's web server at `http://<mate3>/CONFIG.xml` gives everything *else* — firmware versions, nameplate values, configured setpoints, MATE3's own network and data-stream config. Poll at ~5 min intervals and surface the useful bits into HA.

Architecture: the **add-on** polls (it already knows the MATE3 IP from every UDP packet's source), then pushes a new `config_snapshot` event (full curated state on WS connect + every poll) and, if we want, a `config_updated` diff event. The integration stays a reactive WS client.

- [x] **14.1** Add-on: track `last_seen_remote_ip` per MAC in `DeviceRegistry`; this becomes the candidate MATE3 HTTP host. Expose as a method the poller uses. _(2.0.0-dev5)_
- [x] **14.2** Add-on: new `src/mate3_http.py` with `async fetch_config(host)` → parsed dict of curated values (see below). Uses aiohttp; 8 s timeout; logs + returns None on unreachable. _(2.0.0-dev5)_
- [x] **14.3** Add-on: poller task on a 5-min interval (configurable via `config_poll_interval_s` in add-on options, default `300`, `0` disables). Runs after first UDP packet arrives so the host is known. _(2.0.0-dev5)_
- [x] **14.4** Add-on: extend the WS protocol with `config_snapshot` (sent on client connect immediately after `snapshot`, and on every successful poll) and `config_updated` (fires only when parsed dict diverges from the previous). Event shape: `{"type":"config_snapshot", "mac":"...", "config": { ... }}`. _(2.0.0-dev5)_
- [x] **14.5** Integration: handle `config_snapshot` / `config_updated`. Store on `OutbackMate3.config_by_mac[mac]`. Trigger refresh so entity attributes re-read. _(2.0.0-dev5)_
- [x] **14.6** Integration: new `OutbackConfigSensor` class (or extension of existing) for the handful of values that deserve standalone entities — firmware versions, data-stream config, SD card log mode. Everything else becomes attributes on existing `Outback System` / `Outback Inverter N` / `Outback Charge Controller N` devices. _(2.0.0-dev5 first pass: 5 standalone sensors + sw_version on each device; 2.0.0-dev6: shipped the full curated list as individual diagnostic sensors rather than device attributes — 14 system-level + 26 per-inverter + 14 per-CC, all categorized as diagnostic so they stay out of default dashboards but are available for automations)_
- [x] **14.7** Tests: unit test the XML parser against a captured `CONFIG.xml` (obfuscated), and against malformed / partial / empty responses. Add a fixture. _(2.0.0-dev5)_

### Curated value list (what to pull, where it lands)

**Standalone sensors** (one per instance):
- `sensor.mate3_firmware` ← `New_Remote/Firmware`
- `sensor.mate3_<mac>_inverter_<n>_firmware` ← `Port/Device/Firmware` (per inverter)
- `sensor.mate3_<mac>_charge_controller_<n>_firmware` ← `Port/Device/Model/Firmware` (per CC)
- `sensor.mate3_data_stream_target` ← `New_Remote/Network/Data_Stream_IP:Port` (diagnostic — catches "saved but not applied")
- `sensor.mate3_sd_card_log_mode` ← `New_Remote/SD_CARD_Log_Mode` (Disabled / Compact / Excel)

**Outback System device — attributes**:
- `system_type` ← `System@Type`
- `nominal_voltage` ← `Nominal_Voltage`
- `battery_ah_capacity` ← `Battery_AH_Capacity`
- `pv_size_watts` ← `PV_Size_Watts`
- `generator_kw` ← `Generator_KW`
- `max_inverter_output_kw` ← `Max_Inverter_Output_KW`
- `max_charger_output_kw` ← `Max_Charger_Output_KW`
- `data_stream_mode` ← `New_Remote/Data_Stream_Mode`
- `mate3_ip_address` / `mate3_dhcp` / `mate3_gateway` ← `New_Remote/Network/{IP_address,DHCP,Gateway}`
- `system_name` / `installer_name` / `installer_phone` — only populate when non-empty

**Outback Inverter N device — attributes** (from the matching `Port/Device`):
- `type` (e.g. "Split Phase 240V 50/60Hz")
- `inverter_mode` (SEARCH/ON/OFF — configured mode; different from UDP's live `inverter_mode`)
- `low_battery_cut_out_voltage`, `low_battery_cut_in_voltage`, `low_battery_delay`
- `high_battery_cut_out_voltage`, `high_battery_cut_in_voltage`, `high_battery_delay`
- `ac_output_voltage` (120 or 240)
- `charger_mode` (Auto/Off/On)
- `charger_absorb_voltage`, `charger_absorb_time`
- `charger_float_voltage`
- `charger_eq_voltage`, `charger_eq_time`
- `charger_re_float_voltage`, `charger_re_bulk_voltage`
- `grid_tie_mode`, `grid_tie_voltage`, `grid_tie_window` (IEEE/UL)
- `ac_input_priority` (Grid/Generator)
- `ac1_input_type`, `ac1_input_size`, `ac1_min_voltage`, `ac1_max_voltage`
- `ac2_input_type`, `ac2_input_size`, `ac2_min_voltage`, `ac2_max_voltage`
- `stack_mode` (Master/Slave)

**Outback Charge Controller N device — attributes**:
- `model_type` (FM / FM80 / FMX / FlexMax Extreme)
- `charger_absorb_voltage`, `charger_absorb_time`, `charger_absorb_end_amps`
- `charger_float_voltage`
- `charger_rebulk_voltage`
- `charger_eq_voltage`, `charger_eq_time`
- `charger_output_limit` (max A)
- `mppt_mode`, `mppt_sweep_mode`, `mppt_max_sweep`
- `gt_mode` (Grid Tie Enabled/Disabled)

### Deliberately skipped

- Display backlight, button beep, wheel click, serial baud, DNS 1/2, FTP / Telnet ports, OPTICS cloud toggles, MATE3 `Time_Stamp`, free-form `Installer_Notes`.
- The empty `Mini_Grid`, `Grid_Zero`, `AC_Coupled_Mode` sub-blocks only populate when those modes are active. Parser already handles populated-vs-empty.

### Audit & followups

As of 2.0.0-dev8 we capture every useful per-port leaf in CONFIG.xml. 35 system-level leaves remain unexposed, broken into Phase 15 below. Another ~75 (Advance_Generator_Start + Grid_Use/_P2/_P3 schedules) are deferred until a user actually has those features enabled — almost everything is zeros on current test systems.

## Phase 15 — Surface remaining CONFIG.xml system-level fields

Grouped by sub-block:

- [x] **15.1** **Low SOC thresholds**: `Low_SOC_Warning_Percentage`, `Low_SOC_Error_Percentage` — numeric, battery device attributes. _(2.0.0-dev9)_
- [x] **15.2** **Coordination modes**: `CC_Float_Coordination@Mode`, `Multi_Phase_Coordination@Mode` — enum strings, system device. _(2.0.0-dev9)_
- [x] **15.3** **AC coupling**: `AC_Coupled_Control@Mode`, `AC_Coupled_Control/AUX_Output` — enum + int, system device. _(2.0.0-dev9)_
- [x] **15.4** **Global CC output cap**: `Global_Charge_Controller_Output_Control@Mode` + `/Max_Charge_Rate` — enum + `_amp_tenths` (300 → 30.0 A). _(2.0.0-dev9)_
- [x] **15.5** **SunSpec / Modbus**: `Network_Options/SunSpec` + `SunSpec_Port` + `Time_Zone`. _(2.0.0-dev9)_
- [x] **15.6** **FNDC integration**: `FNDC_Charge_Term_Control@Mode`, `FNDC_Sell_Control@Mode`. _(2.0.0-dev9)_
- [x] **15.7** **Grid Mode Schedules 1/2/3**: 9 sensors. _(2.0.0-dev9)_
- [x] **15.8** **High Battery Transfer (HVT/LVC)**: 7 sensors. _(2.0.0-dev9)_
- [x] **15.9** **Load Grid Transfer (load shedding)**: 6 sensors. _(2.0.0-dev9)_
- [x] **15.10** **Advanced Generator Start**: 51 diagnostic sensors (AGS top-level, FNDC Full Charge, Generator Exercise, Load Start, Must Run weekday/weekend, Quiet Time weekday/weekend, SOC Start, 2-min/2-hr/24-hr voltage starts). DC Generator Absorb Voltage + voltage-start voltages use `_volt_tenths`. _(2.0.0-dev10)_
- [x] **15.11** **Grid Use / Grid_Use_P2 / Grid_Use_P3 schedules**: 27 diagnostic sensors across 3 profiles (each with mode + weekday/weekend × drop/use × hour/min). _(2.0.0-dev10)_
- [x] **15.13** Only create config-derived diagnostic entities once the MATE3's HTTP endpoint has been reached at least once (first `config_snapshot`). Prevents a wall of permanently-unavailable entities when the MATE3 is HTTP-unreachable. _(2.0.0-dev9)_
- [x] **15.14** Flip config-derived diagnostic entities to `entity_registry_enabled_default=False`. Users enable the handful they care about; the rest stay hidden and don't churn the recorder. Applies uniformly to every `OutbackConfigDiagnosticSensor` instance (~400 on a populated system). _(2.0.0-dev11)_

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
- [ ] B7 - let's mimick https://github.com/weirded/distributed-esphome in terms of: license, buy me a coffee, style/format of readme and docs.md and the installation instructions (including that nice button) - obviously correcting for the specifics of our add-on.
- [x] B8 - allow orphan MATE3 devices (e.g. from test-fixture traffic) to be removed via HA's Delete Device button, by implementing `async_remove_config_entry_device`. Returns True unless the device is currently present in `mate3.inverters` / `mate3.charge_controllers`. _(2.0.0-dev3)_
- [ ] B9 - now that HACS is gone, make the add-on bundle and deploy the integration into `/config/custom_components/outback_mate3/` on startup so users only have to install one thing. Needs `map: [homeassistant_config:rw]` in the add-on `config.yaml`, a bundled copy of `custom_components/outback_mate3/` inside the add-on's Docker build context, and a shell step in `run.sh` to copy/sync (idempotent — diff first, only overwrite + log when content changes so we don't spam restarts). Until then users install the integration manually per the README.
- [ ] B10 - convert the IP addresses from the strange triple zero display format into a regular IP address format.
- [ ] 