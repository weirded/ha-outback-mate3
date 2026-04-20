# TASKS — Outback MATE3 2.1.0

Decoupling the add-on and integration so the add-on owns the MATE3
protocol end-to-end (D1–D7), plus the bugs that were queued as the
"2.0.1 fast-follow" (F1–F3). All of this ships together as 2.1.0 —
2.0.1 is not being cut separately. Each completed item gets annotated
with `(2.1.0-devN)` — the version running on VM 106 when the work
landed. Used to derive the 2.1.0 CHANGELOG entry.

Dev-version format while this cycle is open: `2.1.0-dev<N>`, bumped in lockstep
across `outback_mate3_addon/config.yaml` and `custom_components/outback_mate3/manifest.json`
via `./scripts/bump-dev-version.sh`.

## Bugs

- [x] **F1** — Inverter battery voltage reads 0. _(2.1.0-dev1; parser was reading
  `values[12]` which is L2 sell current (always 0 on the test system). Radian
  inverter battery voltage actually sits at `values[19]` as integer tenths of a
  volt (`532` → 53.2 V). Fixed in `outback_mate3_addon/src/parser.py`; updated
  `test_inverter_1_values` + `test_inverter_2_values` to assert 53.2 V. Cross-checked
  against a fresh UDP capture from hass-4 (MATE3 at 192.168.200.9) and against
  the Radian GS8048 "Serial Data Stream" PRELIMINARY spec, now checked in at
  `docs/protocol/mate3-radian-udp-stream.pdf`. The system-level battery-voltage
  sensor was already fine — it averages the two CC battery voltages, not the
  inverters — but the per-inverter sensors will now show the correct value.)_

- [x] **F2** — Charge-controller `kwh_today` sensor is stuck at 0. _(2.1.0-dev2;
  same shape as F1: parser was reading `values[13]` which is always `00`. Real
  value lives at `values[6]` as integer tenths of a kWh. Fixed in
  `outback_mate3_addon/src/parser.py`; updated `test_charge_controller_1_values`
  + `test_charge_controller_2_values` to assert 19.4 / 13.2 kWh against the
  t00 fixture. Cross-checked against hass-4 (web UI 3.6 / 1.9 kWh matched
  `values[6]=036/019`) and against the daily-Ah value at `values[12]` —
  19.4 kWh / 53.4 V ≈ 363 Ah ≈ `values[12]=0364`. Pre-existing from the
  upstream integration; 2.0 rewrite carried it over unchanged.)_

- [x] **F3** — Charge-controller daily Ah is not exposed. _(2.1.0-dev3;
  `values[12]` is the MATE3 "Daily Ah" reading, a 4-digit integer (not
  tenths). Parser now emits `daily_ah` in the CC state dict. Integration
  materializes `sensor.mate3_<mac>_charge_controller_<N>_daily_ah` with
  unit `Ah`, `device_class=None`, `state_class=TOTAL_INCREASING` so it
  integrates correctly across the midnight reset. Extended
  `OutbackBaseSensor.__init__` to take an optional `state_class` override
  for cases like this where no HA device_class matches the unit. Added
  parser test assertions (364 / 246 Ah on t00) and an integration test
  asserting the entity attrs. Updated `test_entity_states_snapshot` —
  delta is exactly the one new `daily_ah` row.)_

## Add-on / integration decoupling

Today the integration hard-codes knowledge that derives from the MATE3
UDP/HTTP protocol: field names emitted by
`outback_mate3_addon/src/parser.py`, the spelling and set of mode strings
(`inverting`, `bulk`, ...), per-field unit / device_class / state_class,
and the shape of the MATE3 HTTP config JSON consumed by
`custom_components/outback_mate3/sensor_config.py`. The WS contract
between the two is thin (parsed `state` dicts), but the *semantic*
contract — field names, enum values, units — is duplicated. Goal: make
the add-on the sole source of MATE3 knowledge and reduce the integration
to a generic WS-to-HA renderer. No external users yet, so no migration
shim needed — we just change the WS protocol and ship.

- [x] **D1** — Add-on emits an `entity_schema` WS message (after `hello`,
  before `snapshot`) describing each entity per device kind: `key`, `unit`,
  `device_class`, `state_class`, `entity_category`, `translation_key`, plus
  enum `options` for mode fields. Add `protocol_version` to the `hello`
  message. _(2.1.0-dev4; new `outback_mate3_addon/src/schema.py` holds
  `EntitySpec` dataclasses for every parser-emitted field — inverter (29)
  + charge_controller (9) — with plain-string `device_class` / `state_class`
  / `unit` so the add-on stays HA-agnostic. Enum `options` for
  `inverter_mode` / `ac_mode` / `charge_mode` / `grid_mode` are derived from
  the parser mode maps to keep them in lockstep, and include the `unknown`
  fallback the parser emits. `ws_server.py` now sends hello (with
  `protocol_version: 1`) unconditionally, then `entity_schema`, then
  `snapshot`. Schema coverage is asserted by unit tests that diff the spec
  set against the parser output on the t00 fixture. Backwards-compatible:
  integration currently logs-and-ignores `entity_schema`; D3 consumes it.)_
- [x] **D2** — Publish the MATE3 HTTP config schema the same way — either as
  a field list attached to `config_snapshot` or as a separate
  `config_schema` message — so the ~300-line table in
  `custom_components/outback_mate3/sensor_config.py` is driven by the add-on
  instead of maintained in parallel. _(2.1.0-dev6; new
  `outback_mate3_addon/src/config_schema.py` holds `ConfigEntitySpec`
  dataclasses for every CONFIG.xml-derived diagnostic entity — system (~140
  specs including 3×19 programmatically-generated Grid_Use entries), inverter
  (59), charge-controller (40) — all with plain-string `device_class` / `unit`
  so the add-on stays HA-agnostic. `ws_server.py` now emits both sections in
  one message: `{"type": "entity_schema", "live": {...}, "config": {...}}`.
  Composite `data_stream_target` (`"{ip}:{port}"`) moved from an integration-
  side lambda to a precomputed field in `mate3_http._parse_mate3` so the
  schema stays declarative. Renamed source keys (`configured_type` reads
  `type`, `configured_inverter_mode` reads `inverter_mode`) are expressed via
  `ConfigEntitySpec.source_key`. Integration coordinator stashes both
  sections on `entity_schema` and `config_entity_schema` attributes;
  integration-side rendering switches over in D3. Added 16 add-on unit tests
  + 1 integration test.)_
- [x] **D3** — Rewrite `custom_components/outback_mate3/sensor.py` +
  `sensor_config.py` as a generic factory that materializes entities from
  the received schema. Delete the per-field hard-coded tables. _(2.1.0-dev7;
  `sensor.py` drops from 691 → 387 lines, `sensor_config.py` from 1425 → 186
  lines (−1543 total). `create_device_entities` iterates `entity_schema`
  specs; `OutbackConfigDiagnosticSensor` takes a spec dict and calls
  `_read_value()` generically. `config_flow._probe_ws_url` updated to skip
  `entity_schema` messages. Snapshot gains `kwh_today` CC sensor (was
  accidentally omitted from old hard-coded table). All 33 integration tests +
  112 add-on tests pass.)_
- [x] **D4** — Integration raises a Repairs issue when the add-on's
  `protocol_version` is newer than it knows how to render, removing the
  implicit requirement that both sides stay in version lockstep. _(2.1.0-dev5;
  `custom_components/outback_mate3/const.py` gets `SUPPORTED_PROTOCOL_VERSION = 1`
  + `ISSUE_PROTOCOL_TOO_NEW`. Coordinator now parses `protocol_version` from the
  hello message independently of `addon_version`, stashes the received
  `entity_schema` on the coordinator (consumed in D3), and opens an ERROR-severity
  `protocol_too_new` Repair when the add-on advertises a higher version than
  supported. Added translations for the new issue in `strings.json` +
  `translations/en.json`. Three new integration tests cover: supported version
  raises no issue; newer version raises the issue with placeholders for both
  versions; entity_schema is stored on the coordinator.)_
- [x] **D5** — Translation labels stay in `custom_components/outback_mate3/translations/`
  keyed by the schema's `translation_key` (HA store compliance), but the
  canonical set of keys — including mode enum values — is validated against
  what the add-on advertises so the parser can't emit a string the
  integration has no label for. _(2.1.0-dev8; new `tests/test_translations.py`
  asserts: (1) `strings.json` and `translations/en.json` are byte-identical,
  (2) every live + config `translation_key` has a `.name`, (3) every enum
  option in the live schema has a `.state.<option>` entry (including the
  `unknown` fallback), (4) no orphan labels exist (system aggregates
  `from_grid` / `solar_production` / etc. are allow-listed because they're
  integration-side rollups not advertised by the add-on). Running the tests
  surfaced three D2 regressions that got fixed as part of this work:
  `ags_must_run_*` (9 keys) and `ags_quiet_time_*` (9 keys) were missing
  from `config_schema.py` entirely, `ags_load_start_*_current_threshold`
  was renamed from `*_load_kw` with a wrong unit (Amps vs. actual kW in
  CONFIG.xml), and `ags_soc_start_stop_mode` didn't match the parser's
  `ags_soc_start_mode` key — all reverted/restored so schema keys match
  `mate3_http.py` output. Added `state` blocks for `inverter_mode`
  (17 options), `ac_mode` (4), `charge_mode` (6), `grid_mode` (2), and
  a `kwh_today` label that was missing from strings.json.)_
- [x] **D6** — Reconcile `outback_mate3_addon/bundled_integration/` with the
  decoupled integration (regenerate from the new generic renderer, or drop
  the snapshot once the integration is HA-store-published). _(2.1.0-dev9;
  ran `./scripts/sync-bundled-integration.sh` to mirror the D3/D5 integration
  changes into the bundled copy. sensor.py −387 LOC, sensor_config.py
  −1239 LOC, plus strings.json + en.json enum states picked up from D5.
  install-addon.sh already runs this sync automatically on each deploy, so
  the commit just pins the already-regenerated snapshot. The add-on still
  ships a bundled copy because the integration isn't HA-store-published
  yet; deferring the drop-the-bundle option until it is.)_
- [x] **D7** — Update `docs/architecture.md` + `DOCS.md` to reflect the new
  layering: add-on owns the MATE3 protocol end-to-end (UDP parsing, HTTP
  config polling, entity schema); integration is a generic WS consumer with
  zero MATE3-specific knowledge. _(docs-only; architecture.md gets a new
  "Who owns the MATE3 protocol?" subsection describing `schema.py` +
  `config_schema.py` + the `entity_schema` WS message + how translations
  stay validated against the advertised schema; the Repairs section gains a
  `protocol_too_new` entry and the version section explains why
  protocol_version is decoupled from package version. DOCS.md gets a
  one-paragraph user-facing summary of the same ownership shift.)_

## Release cut — 2.1.0

- [ ] **C1** Final version bump `2.1.0-dev<N>` → `2.1.0` (drop `-dev` suffix)
  across `outback_mate3_addon/config.yaml` and
  `custom_components/outback_mate3/manifest.json`.
- [ ] **C2** Write the `## 2.1.0 — <date>` section in `CHANGELOG.md` from the
  annotated fixes / D-items above.
- [ ] **C3** Tag `v2.1.0` so `.github/workflows/release.yaml` publishes the
  GitHub release with the matching CHANGELOG slice.
