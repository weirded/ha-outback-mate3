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

- [ ] **F2** — Charge-controller `kwh_today` sensor is stuck at 0. Same shape
  as F1: parser reads the wrong CSV field. `values[13]` is always `00`; the
  real value lives at `values[6]` as integer tenths of a kWh. Verified against
  hass-4 captures (port 4 `values[6]=036` while web UI showed 3.6 kWh; port 5
  `values[6]=019` while web showed 1.9 kWh). Fix:
  `kwh_today = float(values[6]) / 10.0`. Pre-existing from the upstream
  integration. See `docs/audit/2.0.1-sensor-audit.md`.

- [ ] **F3** — Charge-controller daily Ah is not exposed. `values[12]` (4-digit)
  is the MATE3 "Daily Ah" reading (69 / 36 Ah on hass-4 at capture time). Add a
  `daily_ah` sensor (unit `Ah`, `device_class=None`, `state_class=total_increasing`
  with a daily reset). See `docs/audit/2.0.1-sensor-audit.md`.

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

- [ ] **D1** — Add-on emits an `entity_schema` WS message (after `hello`,
  before `snapshot`) describing each entity per device kind: `key`, `unit`,
  `device_class`, `state_class`, `entity_category`, `translation_key`, plus
  enum `options` for mode fields. Add `protocol_version` to the `hello`
  message.
- [ ] **D2** — Publish the MATE3 HTTP config schema the same way — either as
  a field list attached to `config_snapshot` or as a separate
  `config_schema` message — so the ~300-line table in
  `custom_components/outback_mate3/sensor_config.py` is driven by the add-on
  instead of maintained in parallel.
- [ ] **D3** — Rewrite `custom_components/outback_mate3/sensor.py` +
  `sensor_config.py` as a generic factory that materializes entities from
  the received schema. Delete the per-field hard-coded tables.
- [ ] **D4** — Integration raises a Repairs issue when the add-on's
  `protocol_version` is newer than it knows how to render, removing the
  implicit requirement that both sides stay in version lockstep.
- [ ] **D5** — Translation labels stay in `custom_components/outback_mate3/translations/`
  keyed by the schema's `translation_key` (HA store compliance), but the
  canonical set of keys — including mode enum values — is validated against
  what the add-on advertises so the parser can't emit a string the
  integration has no label for.
- [ ] **D6** — Reconcile `outback_mate3_addon/bundled_integration/` with the
  decoupled integration (regenerate from the new generic renderer, or drop
  the snapshot once the integration is HA-store-published).
- [ ] **D7** — Update `docs/architecture.md` + `DOCS.md` to reflect the new
  layering: add-on owns the MATE3 protocol end-to-end (UDP parsing, HTTP
  config polling, entity schema); integration is a generic WS consumer with
  zero MATE3-specific knowledge.

## Release cut — 2.1.0

- [ ] **C1** Final version bump `2.1.0-dev<N>` → `2.1.0` (drop `-dev` suffix)
  across `outback_mate3_addon/config.yaml` and
  `custom_components/outback_mate3/manifest.json`.
- [ ] **C2** Write the `## 2.1.0 — <date>` section in `CHANGELOG.md` from the
  annotated fixes / D-items above.
- [ ] **C3** Tag `v2.1.0` so `.github/workflows/release.yaml` publishes the
  GitHub release with the matching CHANGELOG slice.
