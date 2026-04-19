# FAQ

## Does this work without the add-on?

No. The 1.x line worked without an add-on but only on Supervised installs.
2.x deliberately requires the companion add-on because that's the only
reliable way to receive UDP on Home Assistant OS. See
[architecture.md](architecture.md) for why.

## Does this work on Home Assistant Container?

It runs, but you lose the "one install" story — HA Container has no
Supervisor, so the add-on can't run. If you have another way to run a
Python process with host network access (bare Docker, systemd, a
dedicated VM), you can run the add-on's code directly from
`outback_mate3_addon/src/` and point the integration at it over the LAN.
Unsupported, but the WebSocket protocol is stable and documented in the
code.

## Does it support multiple MATE3s?

One MATE3 per Home Assistant instance today. The add-on binds a single UDP
port for the whole host. Multi-MATE3 deployments are rare enough that we
haven't designed for them; file an issue if you need it.

## How do I add a specific setpoint to my dashboard?

Every MATE3 setpoint from `CONFIG.xml` is exposed, but all ~400 of them
start **disabled**. Enable the specific ones you want: **Settings → Devices
& Services → Outback MATE3 → Devices → *your device* → *scroll to
Diagnostic***, click the sensor, toggle **Enabled**. Dashboards pick it up
on the next refresh.

## What about the FlexNet DC (FNDC) battery monitor?

FNDC data comes through the UDP stream as another port. The 2.x integration
parses it but doesn't yet surface a dedicated FNDC device — it lands under
the System device's aggregate metrics. First-class FNDC device support is
planned.

## How often does the integration update?

- **UDP live stream:** every frame (1–2 s cadence from the MATE3).
- **`CONFIG.xml` poll:** every 5 minutes by default, configurable via the
  add-on options. This is what drives the ~400 diagnostic sensors.

## Why does the MATE3 show 5 minutes of staleness on Connected?

`MATE3 Connected` flips off after 300 s without a UDP frame — deliberately
long. A few seconds of packet loss on a wireless LAN is normal and we don't
want the binary sensor flapping. If you genuinely need finer-grained
detection, use the `addon_offline` Repairs signal (60 s grace) or tail the
add-on logs directly.

## Why did version 2.0 drop HACS support?

The add-on *bundles* the matching integration and drops it into
`/config/custom_components/` on first start. HACS would install a second
copy that fights with the bundled one. Dropping HACS was cheaper than
engineering both paths to coexist — and the add-on store covers the same
"install via URL, auto-update" user experience.

If you're upgrading from a HACS-installed 1.x, **remove the HACS copy
first** so it doesn't race with the add-on's bundled 2.x.

## My 1.x config entry — will it migrate?

Yes. The config entry is migrated in place on first 2.x start. Entity
unique IDs are preserved, so **existing dashboards, automations, and Energy
Dashboard configuration continue to work**. The only manual step: the
config flow now asks for a WebSocket URL instead of a UDP port, and any
custom UDP port on the integration side is discarded — move the UDP port
setting (if you changed it) into the add-on's options.

## How do I report a bug?

Include:

1. The version shown on the add-on card **and** the version shown on the
   integration's System Information (three-dot menu on the integration row).
2. Diagnostics JSON — **Settings → Devices & Services → Outback MATE3 →
   three-dot → Download diagnostics**.
3. Add-on logs for the time window where the symptom occurred — `ha apps
   logs local_outback_mate3` or the Log tab on the add-on card.
4. Home Assistant core logs with
   `custom_components.outback_mate3: debug` enabled in `logger`.

Open the issue at
[github.com/weirded/ha-outback-mate3/issues](https://github.com/weirded/ha-outback-mate3/issues).

## How do I contribute?

Read `CONTRIBUTING.md` at the repo root. Development happens against a
HAOS test VM on Proxmox — the `scripts/` directory has the end-to-end
provision → onboard → install → teardown loop.

## Why MIT and not Apache-2.0?

The 1.x code was Apache-2.0; the 2.x rewrite is MIT. No deep reason — MIT
is what the rest of this maintainer's add-ons ship under. The change is
permissive-to-more-permissive, so downstream consumers aren't newly
restricted.
