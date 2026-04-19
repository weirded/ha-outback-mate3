# Troubleshooting

Symptoms and diagnoses, ordered by what new users hit first.

## I don't see a "Discovered: Outback MATE3" card

The add-on announces itself to Supervisor on startup; HA then surfaces the
discovery card under **Settings → Devices & Services**. If it's missing:

1. **Is the add-on running?** Settings → Add-ons → Outback MATE3. State should
   be **Running** (green).
2. **Did you restart Home Assistant after the first add-on start?** The
   bundled integration is dropped into `/config/custom_components/` on the
   add-on's first start, but HA only loads it on the next restart.
3. **Check the add-on log** for lines like `Announced discovery to Supervisor`.
   If those are missing, the add-on couldn't reach Supervisor — usually a
   permissions issue (`hassio_api: true` is required in the add-on
   `config.yaml` — this repository's add-on already declares it).

If discovery is working but you've already added the integration and want
to re-trigger the card, delete the integration's config entry under
**Settings → Devices & Services** and restart the add-on.

## `MATE3 Connected` shows **Off**

This binary sensor flips off after 300 s without any UDP frame. When it's
off, the add-on isn't hearing from your MATE3. Check in this order:

1. **MATE3 data stream config.** On the MATE3: Settings → System → Data
   Stream. `Network Data Stream` must be **Enabled**, `Destination IP` must
   be your HA host's IP, `Destination Port` must match the add-on's
   `udp_port` option (default 57027).
2. **MATE3 firmware quirk.** The MATE3 sometimes "saves" a new Destination
   IP but keeps streaming to the old one until you **fully power-cycle the
   MATE3** (not just the inverter — the MATE3 itself).
3. **Network reachability.** From another machine on the same LAN:
   `nmap -sU -p 57027 <mate3-ip>` won't tell you much (MATE3 sends, not
   listens), but `tcpdump -i <iface> udp port 57027` on the HA host will
   show you whether packets are arriving at all. If they're not, it's a
   network problem (VLAN, firewall, switch port isolation).
4. **Add-on logs.** Settings → Add-ons → Outback MATE3 → Log tab. Look for
   a line like `First UDP datagram from <ip> (<N> bytes)` — it logs at INFO
   only when a new source IP first appears, so a running system logs nothing
   UDP-related after steady state. If you see `Listening for MATE3 UDP on
   0.0.0.0:57027` and nothing else, no packets are arriving.

## All sensors show **Unavailable**

Sensors go Unavailable when the integration's WebSocket is disconnected from
the add-on for more than a few seconds.

1. **Add-on running?** (Same first check as above.)
2. **Correct WebSocket URL?** Settings → Devices & Services → Outback MATE3 →
   Configure. The default `ws://local-outback-mate3:28099/ws` only resolves
   inside Supervisor's Docker network, so if you're running the integration
   from outside HA (unusual), you need the host IP.
3. **Port conflict.** Default WS port 28099 rarely collides, but check
   `netstat -ln | grep 28099` on the host if nothing else explains it.
4. **Check integration logs.** Configure `logger` in `configuration.yaml`:

   ```yaml
   logger:
     default: info
     logs:
       custom_components.outback_mate3: debug
   ```

   Reload, watch the logs, look for `WS connect` / `WS disconnect` lines.

## Repairs issue: **Outback MATE3 add-on offline**

The integration has been unable to reach the add-on's WebSocket for over a
minute. The grace window is deliberately long enough to ride through
Supervisor add-on bounces during updates. If it's raised and won't clear:

1. Open the **Fix** link on the repair — it jumps to the add-on page.
2. Start (or restart) the add-on.
3. The issue auto-clears when the next heartbeat lands.

If the add-on is running and this issue keeps raising, see the "All sensors
show Unavailable" section above — it's the same underlying problem.

## Repairs issue: **Outback MATE3 version drift**

The add-on's self-reported version (sent in a `hello` frame on connect)
doesn't match the integration's version. The two halves are meant to move
in lockstep. To fix:

1. Check both versions: add-on card shows one, Settings → Devices & Services
   → Outback MATE3 → three-dot menu → System Information shows the other.
2. Upgrade whichever is behind. Usually that's the add-on, via the add-on
   store's Update button.
3. Restart Home Assistant if the integration half needed to update.

## Energy Dashboard doesn't pick up the values

The Energy Dashboard needs `state_class: total_increasing` for energy
sensors. The 2.x integration sets that correctly on the `Solar Production
Energy` and derived energy sensors. If the dashboard still isn't picking
them up:

1. **Unit must be `kWh`**, not `Wh` or `W`. Check **Settings → Devices &
   Services → Outback MATE3 → entities list**.
2. **Device class must be `energy`.** Same entities list — it's shown as
   the icon on the entity row.
3. **Reset state_class after a unit change.** If you rolled back from 2.x →
   1.x and back, the state-class may be stale in the recorder. Go to
   **Developer Tools → States**, find the energy sensor, verify its
   attributes. If they're wrong, reload the integration.

## I want to enable a specific setpoint sensor

All ~400 config-derived diagnostic sensors are disabled by default (they're
noisy and most users only want a handful):

1. **Settings → Devices & Services → Outback MATE3 → Devices**.
2. Pick the device (System, a specific Inverter, or a specific Charge
   Controller).
3. Scroll to the Diagnostic section. Click the sensor you want.
4. Toggle **Enabled**.

They become active within 5 minutes (next config poll).

## How do I download diagnostics?

Settings → Devices & Services → Outback MATE3 → three-dot menu → **Download
diagnostics**. The resulting JSON contains the config entry, runtime state,
device list, and both halves' versions — MAC addresses and IPs are redacted
to static placeholders.

Attach that file to any GitHub issue.

## How do I tail add-on logs from the terminal?

If you have SSH or the Terminal & SSH add-on installed:

```bash
ha apps logs local_outback_mate3
```

For the development workflow against a HAOS test VM:

```bash
ssh pve 'docker exec hassio_cli ha apps logs local_outback_mate3'
```

## The MATE3's `CONFIG.xml` isn't reachable

If config-derived diagnostics never appear (everything says "unknown" or is
missing entirely), the add-on can't reach the MATE3's HTTP endpoint:

1. **MATE3 web server enabled?** Settings → System → Web Server on the
   MATE3 display. Must be **Enabled**.
2. **Correct MATE3 IP in add-on options?** The add-on auto-discovers the
   MATE3 IP from the source of incoming UDP packets, so this rarely needs
   overriding.
3. **Firewall between HA and MATE3?** HTTP on port 80. Less common than UDP
   blocking, but possible on segmented networks.

The add-on log will show `http: fetched CONFIG.xml` on success and a
warning with the exception on failure.
