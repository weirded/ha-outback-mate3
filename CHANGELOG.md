# Changelog

All notable changes to the integration and the companion add-on. The two now
share a single version number (`2.0.0-devN` while stabilizing; next cut is
`2.0.0`).

## 2.0.0 — unreleased

The 2.0 cut. First release of the split architecture. The integration no
longer listens for MATE3 UDP packets directly; a new companion
**Outback MATE3** Home Assistant add-on owns the UDP socket (`host_network: true`)
and streams parsed device state to the integration over WebSocket. This
unblocks **Home Assistant OS** — previously impossible because the core
container couldn't bind UDP reliably — and avoids the Supervised-only
workarounds the 1.x line needed.

The integration is now **bundled inside the add-on** and auto-deploys to
`/config/custom_components/outback_mate3/` on the add-on's first start. One
install, one device entry in **Settings → Devices & Services → Discovered**
(via Hass.io discovery), done.

### Breaking changes

- The integration by itself no longer works. Install the companion add-on
  from this repository (**Settings → Add-ons → ⋮ → Repositories** → add
  `https://github.com/weirded/ha-outback-mate3`) and start it.
- The config flow now asks for a WebSocket URL instead of a UDP port. The
  default (`ws://local-outback-mate3:28099/ws`) matches a local add-on
  install on the same HA instance.
- Legacy 1.x config entries migrate automatically to 2.x; any previously
  custom UDP port on the integration side is discarded. Configure the UDP
  port in the add-on's options instead.
- Apache-2.0 → **MIT** license.
- **HACS support dropped.** `hacs.json` and HACS badges/instructions are
  gone. The add-on bundles the integration, so HACS isn't needed. If you
  installed 1.x through HACS, remove the HACS copy first so it doesn't
  fight the add-on-deployed 2.x copy.

### Added

- **Home Assistant add-on** (`outback_mate3_addon/`) with `host_network: true`,
  exposing a WebSocket at `/ws` (default TCP **28099**) with snapshot +
  event-stream semantics. The MATE3 parser + UDP listener now live here.
- **Hass.io auto-discovery**: the add-on announces itself to Supervisor on
  startup; HA surfaces a "Discovered: Outback MATE3" card with one-click Add.
- **Bundled integration auto-deploy**: the add-on drops the matching
  integration copy into `/config/custom_components/outback_mate3/` on startup
  (only when content changed, so it doesn't spam HA restarts).
- **MATE3 HTTP config poll**: every 5 min (configurable) the add-on pulls
  `http://<mate3>/CONFIG.xml` for firmware versions, nameplate, and every
  setpoint. Surfaces ~400 diagnostic sensors covering nameplate, charger
  setpoints, low/high battery cutoffs, grid-tie config, AC1/AC2 input config,
  stack mode, MPPT settings, AUX output, Relay, Diversion, PV Trigger,
  Nite Light, HVT, LGT, Grid Mode Schedules, full Advanced Generator Start
  block, and all three Grid_Use TOU profiles. All disabled-by-default.
- **Connection-health binary sensor** — `binary_sensor.mate3_receiving_data_from_mate3`
  flips off after 300 s without a UDP frame, so automations can notice when
  the MATE3 stops streaming (cable pulled, firmware destination-IP glitch,
  power cycle). See the B19 note below.
- **Reconnect with exponential backoff** (1 s → 30 s cap) when the
  integration's WebSocket drops; aiohttp protocol-level heartbeat catches
  silent network failures.
- **IP-address normalization** in the HTTP config poll — MATE3's
  triple-zero-padded format (`192.168.000.064`) gets converted to canonical
  dotted-quad (`192.168.0.64`).
- **Translated add-on options**: every option has a human-readable name +
  description in Supervisor's UI.
- **Connection-loss visibility** — `async_remove_config_entry_device` lets
  users delete stale MATE3 devices via HA's Delete Device button.
- **Matching add-on icon** (same artwork the integration had).

### Changed

- Entity unique IDs preserved across the migration — existing dashboards,
  automations, and Energy Dashboard configuration continue to work.
- Integration codebase shrank by ~400 lines as the UDP listener and MATE3
  parser moved into the add-on.
- Config-derived diagnostic entities are created only **after** the first
  successful CONFIG.xml poll — no more phantom "unavailable" entities when
  the MATE3's HTTP endpoint isn't reachable.
- Polling loops moved from INFO to DEBUG (only *changes* and *first-seen
  sources* log at INFO now). The standing `info`-level log stays readable.
- WebSocket default port moved from `8099` → `28099` to avoid the common
  8099 collision across other HA add-ons.

### Removed

- HA-OS-incompatibility warning from the README.
- **HACS support** (`hacs.json` + all HACS-related README content).

### Documentation

- README rewritten in the style of the other `weirded` HA add-ons, with an
  accurate "How it works" diagram showing both the add-on and the
  integration running inside Home Assistant, and a sensor list that reflects
  what 2.0 actually ships.
- MATE3 setup notes now call out that the installer code `141` is the
  factory default — use whatever was actually configured at your site.
- Troubleshooting: documented the MATE3 firmware quirk where saved
  "Destination IP" values only apply after a full power cycle.

---

## Pre-2.0 history

The 1.x integration was a single custom component that bound a UDP socket
inside the HA core container. It worked on Supervised installs but not on
HA OS. All 1.x work is frozen; 2.0 supersedes it.
