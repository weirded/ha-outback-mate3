# Changelog

All notable changes to the integration and the companion add-on. Versions
are independent but tracked together here.

## Integration 2.0.0 + Add-on 0.1.0 — 2026-04-18

First release of the split architecture. The integration no longer listens
for MATE3 UDP packets directly; a new companion **Outback MATE3** add-on
owns the UDP socket and streams parsed device state over WebSocket. This
lets the project work on Home Assistant OS, which was previously blocked by
core-container networking constraints.

### Breaking changes

- The integration by itself no longer works. Install the companion add-on
  from this repository (Settings → Add-ons → ⋮ → Repositories → add
  `https://github.com/weirded/ha-outback-mate3`) and start it.
- The config flow now asks for a WebSocket URL instead of a UDP port. The
  default (`ws://local-outback-mate3:8099/ws`) matches a local add-on
  install on the same HA instance.
- Legacy 1.x config entries migrate automatically to 2.x; any previously
  custom UDP port on the integration side is discarded. Configure the UDP
  port in the add-on's options instead.

### Added

- Companion add-on with `host_network: true`, exposing a WebSocket at `/ws`
  with snapshot + event stream semantics.
- Home Assistant Hass.io auto-discovery: when the add-on is running, the
  integration surfaces under Settings → Devices & Services → Discovered
  with a one-click Add.
- Reconnect with exponential backoff (1s → 30s cap) when the WebSocket
  drops.

### Changed

- Entity unique IDs preserved across the migration — existing dashboards,
  automations, and Energy Dashboard configuration continue to work.
- Integration codebase shrank by ~400 lines as the UDP listener and MATE3
  parser moved into the add-on.

### Removed

- HA-OS-incompatibility warning from the README.
- **HACS support.** `hacs.json` and HACS badges / install instructions are
  gone. The integration is no longer distributed through HACS. Users install
  the add-on from this repo (Supervisor → Add-on Store → Repositories), and
  for now copy `custom_components/outback_mate3/` into HA config manually;
  bundling the integration with the add-on is tracked as a follow-up.
