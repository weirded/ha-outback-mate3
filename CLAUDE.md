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
- `scripts/install-addon.sh` — pushes local `outback_mate3_addon/` into the VM
  via qemu-guest-agent and installs/rebuilds via `ha` CLI
- `scripts/install-integration.sh` — pushes local `custom_components/outback_mate3/`
  into the VM and restarts HA core
- `scripts/teardown-haos-vm.sh` — destroys the VM

## Standing rule — always push + commit after each turn

After every turn that changes files in the repo:

1. **Deploy** to the test VM so changes are immediately visible:

    ```sh
    ./scripts/install-addon.sh          # if outback_mate3_addon/ changed
    ./scripts/install-integration.sh    # if custom_components/outback_mate3/ changed
    scp scripts/provision-haos-vm.sh scripts/teardown-haos-vm.sh pve:/root/
                                        # if either of those two scripts changed
    ```

2. **Commit** the changes to the current branch (`weirded/ha-addon-plan`) with
   a clear message.

Do all three unless the user explicitly says not to. Changes the user can't
see sitting on my disk don't count as delivered.
