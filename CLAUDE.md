# Working notes for Claude

## Project layout

- `custom_components/outback_mate3/` — HA custom integration (WebSocket client of the add-on)
- `outback_mate3_addon/` — Home Assistant add-on (UDP listener + WebSocket broadcast server)
- `scripts/` — test-VM lifecycle automation
- `tests/fixtures/mate3_frames/` — real UDP payloads captured from a live MATE3 (device serial obfuscated)
- `docs/superpowers/specs/` — design docs
- `TASKS.md` — phased task breakdown, checkboxes reflect reality

## Test infrastructure

A Home Assistant OS test VM lives on a Proxmox host reachable via `ssh pve`.
Standard identifiers (defaults used across scripts):

- **VMID:** 106, name `haos-test`
- **MAC:** `02:AD:DA:00:00:6A` (derived from VMID → stable DHCP lease)
- **Storage:** `sata-ssd`, **bridge:** `vmbr0`
- **User:** `stefan` / **password:** `Sup3rSecret!` (smoke-test values; not real)
- **Long-lived token:** `~/.config/ha-outback-mate3/token`

Scripts:

- `scripts/provision-haos-vm.sh` — provisions a fresh HAOS VM on pve
- `scripts/onboard-haos.sh` — completes HA onboarding and mints a long-lived token
- `scripts/install-addon.sh` — pushes local `outback_mate3_addon/` into the VM via
  qemu-guest-agent and installs/rebuilds via `ha` CLI
- `scripts/teardown-haos-vm.sh` — destroys the VM

## Rule: keep pve-side scripts in sync

Whenever `scripts/provision-haos-vm.sh` or `scripts/teardown-haos-vm.sh` changes
in this repo, scp them to `pve:/root/` so the Proxmox host has the current
version — those scripts are invoked either directly on pve or via short
`ssh pve bash /root/<name>.sh` wrappers, and stale copies on pve are a known
trap.

```sh
scp scripts/provision-haos-vm.sh scripts/teardown-haos-vm.sh pve:/root/
```

Run this after every turn that modifies either script. Other scripts
(`onboard-haos.sh`, `install-addon.sh`) run locally and talk to pve over SSH,
so they don't need to be copied.
