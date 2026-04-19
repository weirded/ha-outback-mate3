# Changelog

The add-on and its bundled integration share a single version number; see
the top-level [`CHANGELOG.md`](../CHANGELOG.md) for the combined history.

## 2.0.0 — unreleased

First release of the split architecture. The add-on owns the MATE3 UDP
listener (`host_network: true`, default port 57027) and the HTTP
`CONFIG.xml` poller, and exposes a WebSocket broadcast server at `/ws`
(default TCP port **28099**, changed from 8099 in a late pre-release to avoid
common port collisions).

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
