# TASKS — Outback MATE3 2.0.1 fast-follow

Bugfixes and small polish landed on top of 2.0.0. Each completed item gets
annotated with `(2.0.1-devN)` — the version running on VM 106 when the fix
was deployed. Used to derive the 2.0.1 CHANGELOG entry.

Dev-version format while this cycle is open: `2.0.1-dev<N>`, bumped in lockstep
across `outback_mate3_addon/config.yaml` and `custom_components/outback_mate3/manifest.json`
via `./scripts/bump-dev-version.sh`.

## Bugs

- [x] **F1** — Inverter battery voltage reads 0. _(2.0.1-dev2; parser was reading
  `values[12]` which is L2 sell current (always 0 on the test system). Radian
  inverter battery voltage actually sits at `values[19]` as integer tenths of a
  volt (`532` → 53.2 V). Fixed in `outback_mate3_addon/src/parser.py`; updated
  `test_inverter_1_values` + `test_inverter_2_values` to assert 53.2 V. Cross-checked
  against a fresh UDP capture from hass-4 (MATE3 at 192.168.200.9) and against
  the Radian GS8048 "Serial Data Stream" PRELIMINARY spec, now checked in at
  `docs/protocol/mate3-radian-udp-stream.pdf`. The system-level battery-voltage
  sensor was already fine — it averages the two CC battery voltages, not the
  inverters — but the per-inverter sensors will now show the correct value.)_

## Release cut — 2.0.1

- [ ] **C1** Final version bump `2.0.1-dev<N>` → `2.0.1` (drop `-dev` suffix)
  across `outback_mate3_addon/config.yaml` and
  `custom_components/outback_mate3/manifest.json`.
- [ ] **C2** Write the `## 2.0.1 — <date>` section in `CHANGELOG.md` from the
  annotated fixes above.
- [ ] **C3** Tag `v2.0.1` so `.github/workflows/release.yaml` publishes the
  GitHub release with the matching CHANGELOG slice.
