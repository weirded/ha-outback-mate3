# Architecture

This page covers *why* the 2.x integration is split into two halves, and the
design decisions behind the moving parts. For *what* each file does, read the
code — the README's diagram shows the high-level topology.

## Why two halves?

The 1.x line was a single custom integration that bound a UDP socket from
inside the Home Assistant Core container. That works on Supervised installs,
but **Home Assistant OS** isolates the Core container from host networking in
a way that makes UDP reception unreliable — packets are dropped, NAT hides
the real source IP, and there's no supported way to fix it from Core.

2.x solves that by splitting the work:

| Half | Runs as | What it owns |
|---|---|---|
| **Add-on** (`outback_mate3_addon/`) | Privileged add-on container with `host_network: true` | MATE3 protocol end-to-end: UDP listener on port 57027, HTTP config poll of MATE3's `/CONFIG.xml`, entity schema (field names, units, device classes, enum options), WebSocket server on port 28099 |
| **Integration** (`custom_components/outback_mate3/`) | Home Assistant Core | Generic WebSocket-to-HA renderer: consumes the add-on's `entity_schema`, materializes entities, runs the `DataUpdateCoordinator`, config flow, repairs |

The add-on can see UDP packets because it's on the host network. The
integration doesn't need UDP because the add-on hands it parsed state over
a durable WebSocket.

### Who owns the MATE3 protocol?

The add-on. The 2.0 line split the *network stack* (UDP / WebSocket) between
the two halves but left MATE3 *semantics* — field names, units, device
classes, enum strings, the ~400-row diagnostic-entity table derived from
`CONFIG.xml` — duplicated on the integration side. The 2.1 decoupling
(D1–D7) moved all of that into the add-on and reshaped the integration
into a generic schema-driven renderer.

Concretely, the add-on sources live in
`outback_mate3_addon/src/schema.py` (live UDP-derived entities — per-inverter
/ per-charge-controller fields, plus enum `options` for the mode sensors)
and `outback_mate3_addon/src/config_schema.py` (CONFIG.xml-derived
diagnostics — system, MATE3 itself, per-inverter, per-CC). On every WS
client connect, the add-on ships both as one `entity_schema` message with
`live` and `config` sections. The integration stashes them on the
coordinator and `create_device_entities` iterates the specs to build HA
entities — no MATE3-specific tables left in the integration.

Translation labels still live in `custom_components/outback_mate3/strings.json`
(HA store compliance requires them to be shipped with the integration), but
`tests/test_translations.py` validates the *set* of labels against the
advertised schema: every `translation_key` must have a `.name`, every enum
option must have a `.state.<opt>` entry (including the `unknown` fallback),
and orphaned labels fail the build.

## Why bundle the integration inside the add-on?

The add-on drops the matching integration copy into
`/config/custom_components/outback_mate3/` on first start. This means:

- **One install, not two.** Users add the add-on repository and click Install.
  No HACS, no manual file copy.
- **Versions can't drift.** The add-on and integration share a single version
  string. Whatever add-on you installed, the matching integration is in place.
- **Hass.io discovery closes the loop.** The add-on announces itself to
  Supervisor on startup; Home Assistant surfaces a "Discovered: Outback MATE3"
  card and the user clicks Add.

The cost is that the integration can't be installed standalone. That's a
feature, not a bug — a standalone integration without the add-on can't receive
MATE3 data on HA OS anyway.

## Why WebSocket?

The integration needs a *push* stream (MATE3 sends frames every second or
two) and a *request/response* fallback (snapshot fetch on (re)connect, config
on demand). WebSocket gives us both over a single long-lived connection:

- **Push** for live UDP-parsed events, config updates, and heartbeats.
- **Request/response** for the snapshot the add-on sends the moment a client
  connects — no cold-start gaps in the HA UI.
- **Reconnect-safe.** aiohttp's protocol-level heartbeat catches silent
  network failures; the client reconnects with exponential backoff
  (1 s → 30 s cap).

HTTP long-poll would work but costs an extra round-trip per event batch.
Raw TCP would work but we'd reinvent framing.

## Why a bounded queue inside the add-on?

Every UDP datagram produces a list of parsed events. The WebSocket broadcast
fan-out to connected clients (usually one — HA) is async but can stall if a
client's socket is slow. The add-on queues event batches on an
`asyncio.Queue(maxsize=200)` and runs a single consumer task that drains it.

- **Bounded:** 200 batches × ~30 s per-MAC throttle = ~100 min of headroom
  before we drop.
- **Non-blocking enqueue:** `put_nowait` on a full queue increments a drop
  counter and logs a periodic warning. The UDP path never blocks on
  broadcast.
- **Per-client timeout:** each `_send_to` in `broadcast()` runs under
  `asyncio.timeout(10 s)`. A client that exceeds it is dropped from the pool;
  other clients continue unaffected.

This was a post-2.0 fix (PR #6 review item R2/R3). The pre-fix code
spawned unbounded fire-and-forget tasks per datagram, which would have
leaked memory under any backpressure.

## Security model

The add-on's WebSocket server is **unauthenticated**, and deliberately so:

- `host_network: true` restricts the add-on to Supervisor's trusted network.
  The WS port isn't exposed outside the HA host unless the user explicitly
  publishes it.
- The bundled integration connects to `ws://local-outback-mate3:28099/ws` by
  default — a hostname that only resolves inside the Supervisor Docker
  network.
- Adding auth would mean either shipping a per-install shared secret (leaks
  in config dumps) or wiring through HA's long-lived token flow (complex,
  and still pointless on a trusted network).

If you run the integration from outside the HA host, **you need a VPN**.
Don't publish the WS port to the internet.

## Config discovery via `/CONFIG.xml`

The MATE3 has a built-in web server that exposes `CONFIG.xml` — the full
firmware configuration, nameplate, every setpoint. The add-on polls this
every 5 minutes (configurable) and surfaces the result as ~400 diagnostic
sensors.

Why not read the SD card? The SD card stores the same data, but **SD cards
in MATE3s flake out** — media failures, corrupted FAT, write-wear. `CONFIG.xml`
is served from the MATE3's own storage and keeps working when the card doesn't.
The 2.0 rewrite was motivated partly by an SD card failure on the developer's
own MATE3.

The MATE3 returns IP addresses in a triple-zero-padded format
(`192.168.000.064`). The add-on normalizes these to dotted-quad
(`192.168.0.64`) before surfacing them — otherwise HA's IP parsing gags.

## Repairs: add-on-offline, version-drift, protocol-too-new

Home Assistant's Repairs system is how we surface cross-component health.
The integration raises three issues:

- **`addon_offline`** — raised when the WebSocket to the add-on has been down
  for more than 60 s (a grace window so Supervisor add-on bounces don't
  flap it). Links to the add-on management page. Non-fixable from HA; the
  user restarts the add-on.
- **`version_drift`** — raised when the add-on's self-reported `addon_version`
  (sent in a `hello` frame on every (re)connect) doesn't match the
  integration's manifest version. Links to the add-on store. Non-fixable
  from HA; the user upgrades the lagging half.
- **`protocol_too_new`** — raised when the add-on advertises a
  `protocol_version` (also in `hello`) that's higher than the integration's
  `SUPPORTED_PROTOCOL_VERSION`. Separate from `version_drift` so that
  backward-compatible integration releases can pin the protocol they've
  actually been tested against without forcing a version match on every
  deploy.

Neither repair opens a flow — the user's action happens outside HA
(restart the add-on, upgrade one half). A flow-driven fix would just be
noise.

## Single version across both halves

Both `outback_mate3_addon/config.yaml` and
`custom_components/outback_mate3/manifest.json` carry the same version
string. During development it's `<semver>-dev<N>` (e.g. `2.1.0-dev9`); on
release, the `-devN` suffix is stripped and the release workflow validates
that both files match the tag before publishing.

`scripts/bump-dev-version.sh` increments N in lockstep. The CI release
workflow (`.github/workflows/release.yaml`) fails the release if the two
files disagree with the tag.

The *protocol* between the two halves has its own version, decoupled from
the package version. `PROTOCOL_VERSION` in
`outback_mate3_addon/src/ws_server.py` and `SUPPORTED_PROTOCOL_VERSION` in
`custom_components/outback_mate3/const.py` bump only when the wire shape
of `hello` / `entity_schema` / `snapshot` / `state_updated` changes in a
way the integration needs to know about. `version_drift` fires on any
package-version mismatch; `protocol_too_new` fires independently when the
integration can't render the advertised protocol. The separation means
future releases can ship a protocol_version bump that's genuinely
forward-incompatible (add a required field, rename a message) and get a
clear Repairs signal for it, without conflating it with the "please keep
both halves on the same `-devN`" hygiene message.
