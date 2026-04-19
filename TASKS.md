# TASKS — Outback MATE3 2.0.1 fast-follow

Bugfixes and small polish landed on top of 2.0.0. Each completed item gets
annotated with `(2.0.1-devN)` — the version running on VM 106 when the fix
was deployed. Used to derive the 2.0.1 CHANGELOG entry.

Dev-version format while this cycle is open: `2.0.1-dev<N>`, bumped in lockstep
across `outback_mate3_addon/config.yaml` and `custom_components/outback_mate3/manifest.json`
via `./scripts/bump-dev-version.sh`.

## Bugs

- [ ] **F1** — Inverter battery voltage reads 0. `sensor.mate3_<mac>_inverter_<n>_battery_voltage`
  is stuck at 0 V on the live system. CC battery voltage reads correctly, so the
  aggregate/average is also wrong (it's anchored by the zeros from the inverters).
  Suspect: `outback_mate3_addon/src/parser.py:181` reads `float(values[12])` without
  the `/10.0` tenths-of-a-volt scaling the charge-controller branch applies at
  line 197 — but a scaling error would show ~480, not 0, so more likely the index
  is wrong or the field is unpopulated on the Radian inverters we test against.
  Plan: capture a fresh UDP frame from the live MATE3, diff against the
  `tests/fixtures/mate3_frames/` fixtures to find the right index for Radian
  inverter battery voltage, add a regression test asserting a non-zero parsed
  value, fix the parser.

## Release cut — 2.0.1

- [ ] **C1** Final version bump `2.0.1-dev<N>` → `2.0.1` (drop `-dev` suffix)
  across `outback_mate3_addon/config.yaml` and
  `custom_components/outback_mate3/manifest.json`.
- [ ] **C2** Write the `## 2.0.1 — <date>` section in `CHANGELOG.md` from the
  annotated fixes above.
- [ ] **C3** Tag `v2.0.1` so `.github/workflows/release.yaml` publishes the
  GitHub release with the matching CHANGELOG slice.
