# Security policy

## Supported versions

Only the latest `2.x` release line receives fixes. `1.x` is end-of-life; the
2.0 rewrite replaced UDP-inside-HA-core with the add-on model, and 1.x never
worked on HAOS to begin with.

| Version | Supported |
| ------- | --------- |
| 2.x     | ✅ |
| 1.x     | ❌ |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security bugs.

Instead, open a private
[security advisory on GitHub](https://github.com/weirded/ha-outback-mate3/security/advisories/new).
Expect a first response within 7 days.

Relevant surface area to think about when reporting:

- The UDP listener binds on host network and parses untrusted datagrams.
- The WebSocket server on TCP `28099` is intended to be reachable only from
  inside the Supervisor Docker network — exposing it to the LAN is not a
  supported configuration.
- The HTTP config poller fetches `http://<mate3>/CONFIG.xml` with an 8 s
  timeout; a hostile endpoint on that IP could return crafted XML.
- The add-on has `map: homeassistant_config:rw` so it can deploy the bundled
  integration; anything that lets a remote payload steer the copy path is a
  serious bug.

Please include reproduction steps and, where possible, a captured frame /
response that triggers the issue.
