# Changelog

## 0.1.0 — 2026-04-18

Initial release.

- UDP listener on configurable port (default 57027) parses MATE3 streaming
  telemetry.
- WebSocket broadcast server at `/ws` (default port 8099) for the
  Outback MATE3 Home Assistant integration.
- Automatic Supervisor discovery announce on startup — the integration
  surfaces under Settings → Devices & Services → Discovered with no manual
  configuration.
- `host_network: true` so the MATE3 on the LAN can reach this add-on
  consistently across HA OS, Supervised, and Container installs.
- Per-MAC update throttle (configurable, default 30 s) mirrors the
  pre-2.0 integration's behavior.
