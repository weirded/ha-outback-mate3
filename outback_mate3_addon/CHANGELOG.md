# Changelog

The add-on and its bundled integration share a single version number; see
the top-level [`CHANGELOG.md`](../CHANGELOG.md) for the combined history.

## 2.1.0 — 2026-07-17

- **Reliable startup.** If the add-on couldn't refresh the bundled integration
  files in your config folder (for example, when those files were owned by a
  different user), it used to restart in a loop and never begin relaying
  telemetry. It now logs a clear warning and starts normally — the UDP→WS relay
  never depended on that refresh.
- **Corrected telemetry.** Per-inverter battery voltage now reads the real
  value instead of 0 V, and each charge controller now reports the energy it
  generated today (kWh) plus a new daily amp-hour (Ah) total.
- **Add-on owns the MATE3 schema.** The add-on now advertises the full set of
  sensors (names, units, states) to the integration over the WebSocket link, so
  the integration renders them generically and the two stay in lockstep. A
  protocol version is included so a mismatch surfaces as a Home Assistant Repair
  instead of silently mis-rendering.

## 2.0.0 — 2026-04-18

First release of the split architecture. The add-on owns the MATE3 UDP
listener (`host_network: true`, default port 57027) and the HTTP
`CONFIG.xml` poller, and exposes a WebSocket broadcast server at `/ws`
(default TCP port **28099**, chosen to avoid the common 8099 collision across
other HA add-ons).

Notable bits:

- Ships the matching Home Assistant integration bundled under
  `bundled_integration/outback_mate3/` and drops it into
  `/config/custom_components/outback_mate3/` on first start, so users only
  install the add-on.
- Announces itself to Supervisor for Hass.io auto-discovery.
- Per-MAC update throttle (default 30 s) keeps HA's recorder calm despite
  the MATE3's 1 Hz stream.
- CONFIG.xml poll surfaces firmware, nameplate, and every configured
  setpoint as diagnostic sensors (disabled-by-default on the HA side).
- Translated add-on options in Supervisor.
