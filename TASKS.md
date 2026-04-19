# TASKS — Outback MATE3 Home Assistant Add-on (structured WS protocol)

Breakdown for splitting the project into:
- a **Home Assistant add-on** (`outback_mate3_addon/`) that owns UDP I/O, MATE3 parsing, device state, and a WebSocket server emitting typed events, and
- a **slim custom integration** (`custom_components/outback_mate3/`) that connects to the add-on over WebSocket and creates/updates HA entities in response to those events.

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

- [x] **6.1** `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.19 ...` — image built cleanly on Apple Silicon. This pass surfaced the `pre-enrolled-keys=1` / missing `build.yaml` / `init: false` / bashio "null" / macOS `._*` xattr bugs now fixed. _(pre-2.0.0-dev1)_
- [x] **6.2** `docker run -d --rm --name outback-mate3-smoke --network=host -e UDP_PORT=57127 -e WS_PORT=8199 outback-mate3-addon:local` — container came up, logs show "Listening for MATE3 UDP on 0.0.0.0:57127" and "WebSocket server listening on 0.0.0.0:8199/ws". _(pre-2.0.0-dev1)_
- [x] **6.3** Python one-liner sending `telemetry_00.bin` via `socket.sendto` to `127.0.0.1:57127` — datagram picked up, parser ran, events broadcast. _(pre-2.0.0-dev1)_
- [x] **6.4** aiohttp WS client against `ws://127.0.0.1:8199/ws` — received empty snapshot on connect, then 4 `device_added` events (2 inverters + 2 charge controllers) with correct `kind` / `index` / `state`. _(pre-2.0.0-dev1)_

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

- [x] **9.1** PHACC installed; `pytest.ini` sets `asyncio_mode=auto`; `tests/conftest.py` loads the PHACC plugin + autouses `enable_custom_integrations`; `outback_mate3_addon/tests/conftest.py` re-enables sockets (PHACC ships pytest-socket which blocks the network). _(2.0.0-dev10)_
- [x] **9.2** `_FakeAddOn` fixture in `tests/test_integration.py` — aiohttp `TestServer` exposing `/ws`, each new client receives a scripted list of canned messages, `broadcast()` fans out new messages to connected clients live. _(2.0.0-dev10)_
- [x] **9.3** `test_snapshot_creates_udp_entities` + `test_state_updated_refreshes_entities` — after snapshot, inverter 1's `grid_power` reads 500; a `state_updated` mutates it to -300 and the entity reflects it. _(2.0.0-dev10)_
- [x] **9.4** `test_reconnects_after_addon_drops_ws` — fake server closes all clients mid-stream, integration reconnects, the next snapshot payload (with `grid_power=999`) lands on the entity. Plus `test_config_snapshot_only_creates_diagnostics_after_poll` asserts the 15.13 gating via the entity registry (since config sensors are disabled-by-default per 15.14). _(2.0.0-dev10, updated 2.0.0-dev11)_

## Phase 10 — Docs & release

- [x] **10.1** Update `README.md`: remove the "does not work on HA OS" warning, add sections explaining the two-part install (add-on from repo URL, integration from HACS), and add a breaking-change note for existing users.
- [x] **10.2** Add `outback_mate3_addon/README.md` explaining options, what to point MATE3 at (host IP:57027), and troubleshooting.
- [x] **10.3** ~~Check `hacs.json`~~ → Dropped HACS entirely (`hacs.json` removed, README badges and install instructions updated, CHANGELOG notes the removal). _(2.0.0-dev4)_
- [x] **10.4** Write release notes / CHANGELOG for the 2.0 cut.

## Phase 11 — End-to-end validation on real HA OS

- [ ] **11.1** Install the add-on on an HA OS instance by adding this repo's URL to Supervisor. _(gated on publishing to `main` — Supervisor's store clones the default branch, which as of 2.0.0-dev12 still has the pre-2.0 layout. Validated the store-level handshake: `ha store add https://github.com/weirded/ha-outback-mate3` correctly rejects "not a valid app repository" today, proving the check is active. Flip to done on the first run against a main-branch HEAD that contains `outback_mate3_addon/` + `repository.yaml`. Fast-forward `weirded/ha-addon-plan` → `main` whenever you're ready to cut the release.)_
- [x] **11.2** ~~Install the integration via HACS~~ — HACS support removed in 2.0 (B7/10.3). The integration now ships bundled inside the add-on and gets deployed to `/config/custom_components/outback_mate3/` automatically on first add-on start (B9 / 2.0.0-dev12). Replaces this item entirely.
- [x] **11.3** Configure MATE3 to stream to the HA host IP on port 57027. _(2.0.0-dev2, verified via tcpdump)_
- [x] **11.4** Verify entities appear with correct values; cross-check against the MATE3 display. _(2.0.0-dev10 — UDP-stream entities match live MATE3 values; every config-derived diagnostic sensor spot-checked against `http://<mate3>/CONFIG.xml` AND the Radian + CC settings screenshots from the MATE3 web UI: absorb V 55.2 / 55.4, low-batt cut-out 48.0 V, AC1 input size 200.0 A, CC output limit 80.0 A, MPPT upick 77 %, AUX PV trigger 140.0 V, Nite Light threshold 10.0 V, HVT disconnect 52.0 V, AGS DC Gen absorb 76.0 V, Grid_Use mode Disabled — all match. IP normalization from B10 verified: mate3_ip_address `192.168.0.64`, gateway `192.168.0.1`.)_
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
- [x] **15.10** **Advanced Generator Start**: the full 51-leaf AGS block (enable mode, VDC/SOC/load/temp/exercise/quiet-time triggers, generator profile, run-limits, warm-up/cool-down, DC-gen absorb/float/bulk/EQ setpoints). Pulled as diagnostic sensors on the System device. Disabled-by-default per 15.14. _(2.0.0-dev11 — spot-checked against Radian AGS screen: DC-Gen absorb 76.0 V, bulk 74.4 V, float 65.0 V, max run 240 min, quiet-time 2200–0700, all match.)_
- [x] **15.11** **Grid Use / Grid_Use_P2 / Grid_Use_P3 schedules**: Grid_Use enable, grid-use/grid-drop weekday+weekend hours, sell hours, voltage/SOC thresholds — all three profiles as 19 diagnostic sensors on the System device. Mostly zeros on systems without TOU configured, but the enum `grid_use_mode` gives a quick "Disabled" indicator without users having to enable the others. _(2.0.0-dev11 — Grid_Use mode reads "Disabled" on the test system, confirming the field is populated correctly even when the schedule is inactive.)_
- [x] **15.13** Only create config-derived diagnostic entities once the MATE3's HTTP endpoint has been reached at least once (first `config_snapshot`). Prevents a wall of permanently-unavailable entities when the MATE3 is HTTP-unreachable. _(2.0.0-dev9)_
- [x] **15.14** Flip config-derived diagnostic entities to `entity_registry_enabled_default=False` after confirming values populate correctly. Keeps the recorder quiet — users enable only the handful they care about. _(2.0.0-dev11 — `OutbackConfigDiagnosticSensor` base class sets `_attr_entity_registry_enabled_default = False`; every config-poll sensor inherits it. Firmware sensors stay enabled-by-default because they're the one set users actually want visible. Verified on VM 106: config sensors show as "Disabled" in the device page but the values are correct when enabled.)_

## Phase 12 — Hass.io discovery (auto-suggest the add-on to the integration)

When the add-on is running, HA should automatically surface the integration under **Settings → Devices & Services → Discovered**, pre-filled with the add-on's WebSocket URL. No manual config flow needed.

- [x] **12.1** Add `hassio_api: true` and `discovery: [outback_mate3]` to `outback_mate3_addon/config.yaml`. The first grants the add-on permission to talk to Supervisor; the second declares which service names it may announce.
- [x] **12.2** Implement discovery announce in `outback_mate3_addon/src/main.py`. On startup, if `SUPERVISOR_TOKEN` is set, POST to `http://supervisor/discovery` with `{"service": "outback_mate3", "config": {"host": "<addon-hostname>", "port": <ws_port>}}`. Store the returned UUID. On graceful shutdown, DELETE `/discovery/{uuid}`. Failures log and continue — running outside HA (plain Docker) must still work.
- [x] **12.3** Set `"hassio": true` in `custom_components/outback_mate3/manifest.json` so HA routes Hass.io discovery events for our service name to this integration.
- [x] **12.4** Implement `async_step_hassio(discovery_info: HassioServiceInfo)` in `custom_components/outback_mate3/config_flow.py`. Build the WS URL from `discovery_info.config`, set a stable unique_id so repeated announces don't create duplicates (and update the URL if it changed), show a confirmation step.
- [x] **12.5** Add strings for the `hassio_confirm` step to `custom_components/outback_mate3/translations/en.json`.
- [x] **12.6** Verify end-to-end on the HAOS test VM: after `./scripts/install-addon.sh`, a "Discovered: Outback MATE3" notification appears in HA within a few seconds; clicking through auto-creates an entry with the correct WS URL.

## Bugfixes/Tweaks

_Each completed item is annotated with `(vX.Y.Z-devN)` — the add-on / integration version running on VM 106 when the fix was deployed. Used to derive the changelog._

- [x] B1 - we don't need to describe the WebSocket protocol on docs.md. _(2.0.0-dev1)_
- [x] B2 - we are missing a changelog; let's fix that.  _(2.0.0-dev1)_
- [x] B3 - the add-on is missing the icon that we had for the integration before. Let's fix that also. _(2.0.0-dev1)_
- [x] B4 - let's make the version of the add-on and integration match always. _(2.0.0-dev1)_
- [x] B5 - while we develop, let's append a .devN suffix to the version and increment N on each turn, so that I can see when we are running a newer version. _(2.0.0-dev1)_
- [x] B6 - after each turn, update TASKS.md, noting the specific version that fixed the task. We are going to use tasks.md to derive a changelog. _(2.0.0-dev1)_
- [x] B7 - let's mimick https://github.com/weirded/distributed-esphome in terms of: license, buy me a coffee, style/format of readme and docs.md and the installation instructions (including that nice button) - obviously correcting for the specifics of our add-on. _(2.0.0-dev12; LICENSE switched from Apache-2.0 to MIT, README + DOCS.md restructured with MIT + Buy-Me-a-Coffee badges, one-click "Add repository to my Home Assistant" button, distributed-esphome section ordering)_
- [x] B8 - allow orphan MATE3 devices (e.g. from test-fixture traffic) to be removed via HA's Delete Device button, by implementing `async_remove_config_entry_device`. Returns True unless the device is currently present in `mate3.inverters` / `mate3.charge_controllers`. _(2.0.0-dev3)_
- [x] B9 - now that HACS is gone, make the add-on bundle and deploy the integration into `/config/custom_components/outback_mate3/` on startup so users only have to install one thing. _(2.0.0-dev12; `outback_mate3_addon/bundled_integration/outback_mate3/` is a synced copy of `custom_components/outback_mate3/`, kept current by `scripts/sync-bundled-integration.sh` which `install-addon.sh` calls before packaging. Dockerfile COPYs it to `/opt/integration/`; `run.sh` does a `diff -rq` + `cp -R` on startup, logs only when content actually changes so HA doesn't get restart-spam. `config.yaml` now has `map: [homeassistant_config:rw]`.)_
- [x] B10 - convert the IP addresses from the strange triple zero display format into a regular IP address format. _(2.0.0-dev12; new `_ipv4()` helper in `mate3_http.py` strips leading zeros from each octet — `192.168.000.064` becomes `192.168.0.64`. Applied to `ip_address`, `netmask`, `gateway`, `data_stream_ip`. Fail-open on anything that doesn't parse cleanly.)_
- [x] B11 - fix the "How it works" diagram so it shows both the add-on and the integration (plus HA around them). _(2.0.0-dev14; new ASCII diagram with two boxes side-by-side under an HAOS rule, arrow from the MATE3 on the LAN feeding UDP into the add-on, a ws:28099/ws arrow between add-on and integration, and an outgoing arrow from the integration into the HA UI / Energy Dashboard. Bumps home the fact that **both** halves run inside HA.)_
- [x] B12 - rewrite the README "Available Sensors" section to match what 2.0 ships. _(2.0.0-dev14; lead paragraph explains the three device types + enabled-vs-diagnostic split, System bullets call out the new `Receiving Data from MATE3` binary sensor + all the config-poll diagnostic blocks we surface, Inverter + CC bullets also list their diagnostic setpoints.)_
- [x] B13 - CHANGELOG now has a proper 2.0.0 section. _(2.0.0-dev14; rewrote top-level CHANGELOG.md with a single combined 2.0.0 entry covering breaking changes, added/changed/removed, and the connectivity-binary-sensor + translated-options additions. Also cleaned up `outback_mate3_addon/CHANGELOG.md` to reference the top-level one rather than pretending it's a standalone 0.1.0 ship.)_
- [x] B14 - installer-code note. _(2.0.0-dev14; README and DOCS.md now say the code is the factory default and that whoever commissioned the system may have changed it, rather than implying 141 is universal.)_
- [x] B15 - WS port moved `8099 → 28099`. _(2.0.0-dev14; changed in `config.yaml`, `src/main.py`'s fallback, `DEFAULT_URL` on the integration, README diagram + install-defaults bullet, DOCS.md options table, install-addon.sh's "done" footer, and the translated `network:` block in the new `translations/en.yaml`. 28099 is outside Linux's default ephemeral range, uncommon among other HA add-ons, and keeps the trailing "99" mnemonic.)_
- [x] B16 - removed the SD-card bullet from DOCS.md's Troubleshooting. _(2.0.0-dev14)_
- [x] B17 - documented every add-on option. _(2.0.0-dev14; new `outback_mate3_addon/translations/en.yaml` with `configuration:` + `network:` blocks so Supervisor's UI shows a human-readable name + description on each option (and labels both listening ports).)_
- [x] B18 - toned down polling-loop log noise. _(2.0.0-dev14; in `src/config_poller.py`, only `changed` config polls log at INFO (they broadcast), unchanged polls drop to DEBUG. On the integration side, `_ws_loop` only WARNs on the first consecutive connect failure per disconnect and drops to DEBUG for subsequent retries, so a stopped add-on doesn't produce a WARN every <backoff>s. Audited the other INFO logs — they're startup/shutdown/first-seen-source only, no periodic spam.)_
- [x] B19 - `binary_sensor.mate3_system_receiving_data` ("Receiving Data from MATE3"). _(2.0.0-dev14; new `custom_components/outback_mate3/binary_sensor.py` platform — `BinarySensorDeviceClass.CONNECTIVITY`, on the Outback System device. `OutbackMate3.last_udp_at` monotonic timestamp set in `_apply_device` for snapshot/device_added/state_updated (NOT config_snapshot — those come from HTTP, not UDP). Sensor's `is_on` returns True iff `last_udp_at` is not None and less than 300 s old. Two refresh paths: the coordinator listener catches off→on instantly, and a 30-second `async_track_time_interval` catches on→off when the stream goes silent. Two new tests in `tests/test_integration.py` cover both the flip-on-snapshot and the stays-off-when-only-config-snapshot cases.)_
- [x] B20 Add MyPy to the entire codebase and make sure it passes. _(2.0.0-dev21; added `[tool.mypy]` block to `pyproject.toml` (python 3.12, `explicit_package_bases = true` so `custom_components/outback_mate3` + `tests/` coexist, `mypy_path = "outback_mate3_addon"` so the add-on's `src.*` imports resolve, excludes the `bundled_integration/` copy, silences `pytest_homeassistant_custom_component` + `pytest_socket` missing-stubs noise). Fixed 268→0 integration errors by swapping `FlowResult` → `ConfigFlowResult` in config_flow, `homeassistant.helpers.entity.DeviceInfo` → `homeassistant.helpers.device_registry.DeviceInfo` in sensor.py / sensor_config.py / binary_sensor.py, parameterizing `CoordinatorEntity[OutbackMate3]`, annotating `entities: list[SensorEntity]`, casting the battery-voltage average to `float`, annotating the two untyped `native_value` properties with `StateType`, and annotating `SNAPSHOT_PAYLOAD` / `CONFIG_PAYLOAD` / `_FakeAddOn.url` in tests. Extended `.github/workflows/lint.yaml` with a `mypy` job that runs two passes (integration+tests, add-on+tests — unavoidable because both trees expose a module named `tests.conftest`). Add-on source was already clean on default mypy and needed no code changes.)_
- [x] B21 Rename Receiving Data from MATE3 to MATE3 Connected. _(2.0.0-dev20; renamed class `OutbackReceivingDataSensor` → `OutbackMate3ConnectedSensor`; switched from hardcoded `_attr_name` to `_attr_translation_key = "mate3_connected"` so the display name is canonically translated; unique_id `{DOMAIN}_system_receiving_data` → `{DOMAIN}_system_connected`; entity_id `binary_sensor.mate3_system_receiving_data` → `binary_sensor.mate3_system_connected`. Updated strings.json / translations/en.json (`mate3_receiving_data` → `mate3_connected`, "MATE3 Connected"), README bullet, comments in `__init__.py` + `const.py`, and the two binary-sensor tests. Existing deployments will see a fresh entity appear with the new entity_id/unique_id and the old one orphan — intentional per "don't worry about backwards compat".)_

## Phase 16 — Gold readiness, Wave 1 (foundation)

_Low-risk additive changes that unblock later gold work. Target: Bronze on the HA Integration Quality Scale + community-file hygiene._

### Integration

- [x] **16.1** Declare `quality_scale: "bronze"` in `custom_components/outback_mate3/manifest.json`. _(2.0.0-dev1)_
- [x] **16.2** Add empty `custom_components/outback_mate3/py.typed` marker so downstream type-checkers honor our annotations. _(2.0.0-dev1)_
- [x] **16.3** Create `custom_components/outback_mate3/const.py` and move scattered literals (domain, default WS URL, backoff, heartbeat, entity-timeout constants) into it. No behavior change. _(2.0.0-dev16)_
- [x] **16.4** Switch the `solar_production_energy` sensor (and any other energy totalizers) from `SensorStateClass.MEASUREMENT` to `SensorStateClass.TOTAL_INCREASING` so the Energy Dashboard treats them as totalizers. Also fixes ENUM sensors which were incorrectly advertising `state_class=measurement`. _(2.0.0-dev16)_
- [x] **16.5** Set `entity_category = EntityCategory.DIAGNOSTIC` on every config-derived 400+ sensor — already satisfied via `OutbackConfigDiagnosticSensor._attr_entity_category` (no change needed). _(2.0.0-dev16)_

### Add-on

- [x] **16.6** Add `outback_mate3_addon/apparmor.txt` — minimal permissive profile (network in/out, `/app` rx, `/homeassistant` rw, deny everything else outside the container rootfs). _(2.0.0-dev1)_
- [x] **16.7** Add `HEALTHCHECK` to `outback_mate3_addon/Dockerfile` that probes TCP `28099` (the WS port). _(2.0.0-dev1)_
- [x] **16.8** Add `io.hass.*` OCI labels to `outback_mate3_addon/Dockerfile` (`io.hass.version`, `io.hass.type=addon`, `io.hass.arch`, `maintainer`). _(2.0.0-dev1)_
- [x] **16.9** Pin `aiohttp` to an exact version in `outback_mate3_addon/requirements.txt` — `aiohttp==3.11.11`. _(2.0.0-dev1)_

### Repo infrastructure

- [x] **16.10** Add `CODEOWNERS` at repo root (single entry for `@weirded`). _(2.0.0-dev1)_
- [x] **16.11** Add `SECURITY.md` — reporting instructions + supported versions. _(2.0.0-dev1)_
- [x] **16.12** Add `.github/FUNDING.yml` — Buy Me a Coffee as first-class GitHub funding link. _(2.0.0-dev1)_
- [x] **16.13** Add `.github/ISSUE_TEMPLATE/bug.yaml` and `.github/ISSUE_TEMPLATE/feature.yaml` (+ `config.yml` to direct questions to the HA forum). _(2.0.0-dev1)_
- [x] **16.14** Add `.github/PULL_REQUEST_TEMPLATE.md`. _(2.0.0-dev1)_
- [x] **16.15** Add `pyproject.toml` at repo root with `[tool.ruff]` + `[tool.pytest.ini_options]` config (migrated from `pytest.ini`, which was deleted). _(2.0.0-dev1)_
- [x] **16.16** Add `.github/workflows/lint.yaml` — runs `ruff check` on push / PR. Rule-set selects E/W/F/I/UP/B/SIM/ASYNC/RUF with pragmatic ignores; the ruff auto-fixes landed across 19 files as part of enabling this. Format-check is intentionally off for now (Phase 17). _(2.0.0-dev1)_
- [x] **16.17** Add `.github/workflows/test.yaml` — runs pytest for `tests/` (integration) and `outback_mate3_addon/tests/` (add-on). Uses new `requirements_test.txt`. _(2.0.0-dev1)_

## Phase 17 — Gold readiness, Wave 2 (gold criteria)

_Bigger-surface changes that move the integration from Bronze toward Gold._

- [x] **17.1** Create `custom_components/outback_mate3/diagnostics.py` — `async_get_config_entry_diagnostics` returning entry data + coordinator snapshot with sensitive-field redaction. _(2.0.0-dev17)_
- [x] **17.2** Create `custom_components/outback_mate3/strings.json` with translatable names for entity classes + exceptions; regenerate `translations/en.json` from it. _(2.0.0-dev17)_
- [x] **17.3** Add `async_step_reconfigure(self, user_input)` to `custom_components/outback_mate3/config_flow.py` so users can change the WS URL post-setup without deleting/recreating the entry. _(2.0.0-dev17)_
- [x] **17.4** Split `custom_components/outback_mate3/sensor.py` into `sensor.py` (live UDP sensors) + `sensor_config.py` (400+ config-derived diagnostic sensors). `sensor.py` shrank from 992 lines to 390; `sensor_config.py` owns `OutbackConfigDiagnosticSensor`, the declarative `_SYSTEM_/_INVERTER_/_CC_CONFIG_SENSORS` tables, the `_sys` / `_m3` / `_inv` / `_cc` getter helpers, and `create_config_entities`. `__init__.py`'s lazy import in `_apply_config` now points at `.sensor_config`. _(2.0.0-dev18)_
- [x] **17.5** Parameterize `DataUpdateCoordinator[None]` and migrate from `hass.data[DOMAIN][entry_id]` to `ConfigEntry.runtime_data`. Added `type MateConfigEntry = ConfigEntry[OutbackMate3]` alias re-exported from `__init__.py` so platforms get typed access. _(2.0.0-dev17)_
- [x] **17.6** Replace broad `except Exception` with narrow `(aiohttp.ClientError, TimeoutError, OSError)` for transient WS failures in `__init__.py`. _(2.0.0-dev17)_
- [x] **17.7** Expand `tests/test_integration.py` from 6 tests to 22. Added coverage for: config-flow user happy path, user-step probe errors (`cannot_connect` / `timeout` / `bad_handshake` / `unknown` via parametrize), duplicate abort, hassio-confirm happy path, hassio rediscovery updating URL in place, reconfigure happy path + reconfigure probe error, v1→v2 `async_migrate_entry`, unknown WS message type, malformed `config_snapshot` payloads, stale-device removal allowed, live-device removal blocked, and diagnostics snapshot. _(2.0.0-dev18)_
- [ ] **17.8** Add `outback_mate3_addon/logo.png` (512×512 PNG).
- [x] **17.9** Add `.github/workflows/builder.yaml` — multi-arch add-on build via `home-assistant/builder` action (all 5 archs). _(2.0.0-dev17)_
- [x] **17.10** Add `.github/dependabot.yml` — GitHub Actions + pip ecosystems. _(2.0.0-dev17)_
- [x] **17.11** Add `.pre-commit-config.yaml` + `.editorconfig`. _(2.0.0-dev17)_
- [x] **17.12** Flip `quality_scale` from `"bronze"` to `"silver"` now that 17.1–17.7 have landed. Revisit `"gold"` after running through the HA checklist entry-by-entry. _(2.0.0-dev18)_

### Bug fixes surfaced while doing Phase 17
- [x] **17.A** `create_device_entities` would raise `KeyError` when a snapshot was processed in order (inverter first, charge_controller second) because it indexed both `mate3.inverters[mac]` and `mate3.charge_controllers[mac]` unconditionally. Switched both iterations to `.get(mac, {})`. _(2.0.0-dev17)_

## Phase 18 — Platinum-adjacent polish (Wave 3)

- [x] **18.1** Raise two Home Assistant Repairs issues: `addon_offline` (surfaces after a `ADDON_OFFLINE_GRACE_S = 60 s` grace so brief Supervisor bounces don't flap it) and `version_drift` (raised when the add-on's self-reported `addon_version` doesn't match the integration's manifest version). Both are non-fixable `ir.IssueSeverity.WARNING` issues driven from coordinator connect/disconnect transitions — no `repairs.py` needed for a flow since the user's action (restart add-on, upgrade one half) happens outside HA. WS protocol gained a `hello` frame (add-on → integration) carrying `addon_version`; add-on reads its version via `bashio::addon.version` in `run.sh` → `ADDON_VERSION` env var → `WSServer(addon_version=...)`. `translations/en.json` + `strings.json` carry the two `issues` translation keys with `{url}` and `{integration_version}/{addon_version}` placeholders. Diagnostics snapshot now exposes both versions. _(2.0.0-dev19)_
- [ ] **18.2** Add snapshot tests via `syrupy` for entity state.
- [ ] **18.3** Add `async_step_reauth(self, entry_data)` to config_flow (no-op until auth is added, but wired for forward compat).
- [ ] **18.4** Finish B20 — MyPy strict across both components, wire into `.github/workflows/lint.yaml`.
- [ ] **18.5** Build user-facing `docs/` (architecture, troubleshooting, FAQ) beyond the README.
- [ ] **18.6** Add `.github/workflows/release.yaml` — tag-triggered release that validates version bump across add-on + integration.

## Post-2.0 follow-ups (from PR #6 review)

Copilot reviewed the 2.0 PR and flagged 10 items. All ten were addressed as part of cutting 2.0.0 — two user-facing doc bugs inline with the version bump, the eight robustness / cleanup items in a focused follow-up pass.

- [x] **R1** — `CHANGELOG.md:56` referenced `binary_sensor.mate3_receiving_data_from_mate3`, but the code ships `binary_sensor.mate3_system_receiving_data`. _(2.0.0 — fixed at cut)_
- [x] **R2** — `outback_mate3_addon/src/udp_listener.py:80` spawned an unbounded fire-and-forget `asyncio.create_task(_safe_broadcast(...))` per datagram. _(2.0.0 — refactored to a bounded `asyncio.Queue` on `WSServer`. UDP callback and config poller both call `server.enqueue_broadcast(events)` (non-blocking `put_nowait`); `main.py` runs one `server.run_broadcaster(stop)` consumer task that drains the queue and serializes fan-out ordering. Queue capacity 200 batches — ~100 min of stall headroom vs the 30 s per-MAC throttle. Drop counter + periodic warning when the consumer falls behind. Tests cover both the happy path and the full-queue drop case.)_
- [x] **R3** — `outback_mate3_addon/src/ws_server.py:103` sent messages sequentially; one slow client stalled all peers. _(2.0.0 — `broadcast()` now `asyncio.gather`s per-client `_send_to(ws, messages)` calls, each wrapped in an `asyncio.timeout(_SEND_TIMEOUT_S)` (10 s default). Clients that error or time out are dropped from `_clients`; peers continue unaffected. New test `test_one_slow_client_does_not_stall_other_clients` monkey-patches one client's `send_json` to sleep past the timeout, then asserts broadcast returns in < 1 s and the slow client is evicted.)_
- [x] **R4** — top-level + add-on CHANGELOG headers were stamped "unreleased" / "next cut is 2.0.0". _(2.0.0 — both now say `2.0.0 — 2026-04-18` and the guide text updated accordingly)_
- [x] **R5** — `outback_mate3_addon/src/parser.py:86`'s filter `blocks.startswith("0")` silently dropped device IDs that don't start with `"0"` (port 10+). _(2.0.0 — switched to a structural regex `_DEVICE_BLOCK = re.compile(r"^\d+,\d+")`. New test `test_port_10_charge_controller_is_not_dropped` builds a synthetic frame with a CC on port 10 and asserts it parses through. A second regression test pins down that malformed trailing fragments still get skipped.)_
- [x] **R6** — `tests/test_integration.py:11`: unused `from collections import deque` import. _(2.0.0 — removed)_
- [x] **R7** — `tests/test_integration.py:197` + `:326`: `st.state` accessed without `st is not None` check; a missing entity would raise an opaque `AttributeError`. _(2.0.0 — both loops now `assert st is not None` with a descriptive "entity vanished" message before the state comparison, and the state assertion itself includes the last-observed state in its message.)_
- [x] **R8, R9** — `scripts/install-addon.sh` and `scripts/install-integration.sh` hard-coded `/nodes/pve/…` in `pvesh` API paths. _(2.0.0 — both scripts now accept `PVE_NODE`, falling back to auto-detect via `pvesh get /nodes --output-format json`. Every `pvesh` call threads `PVE_NODE` into the remote bash blocks via positional args so clusters / custom node names work without code changes.)_
- [x] **R10** — `docs/superpowers/specs/2026-04-17-ha-addon-design.md` was stale vs the implementation. _(2.0.0 — deleted. The spec served its purpose during design; README now carries the architecture diagram and user-facing explanation, CHANGELOG has the decision history, and the code is authoritative for everything else. Keeping a second parallel description in sync was exactly the rot this review flagged, so we dropped the artifact rather than re-writing it. The empty `docs/` directory was removed too.)_ 