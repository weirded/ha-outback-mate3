# Working notes for Claude

## Project layout

- `custom_components/outback_mate3/` — HA custom integration (WebSocket client of the add-on)
- `outback_mate3_addon/` — Home Assistant add-on (UDP listener + WebSocket broadcast server)
- `scripts/` — test-VM lifecycle automation
- `tests/fixtures/mate3_frames/` — real UDP payloads captured from a live MATE3 (device serial obfuscated)
- `archive/TASKS-2.0.0.md` — phased task breakdown for the 2.0 cycle
  (checkboxes reflect reality; a new `TASKS.md` gets opened at the repo
  root when the next release cycle starts)

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
- `scripts/bump-dev-version.sh` — increments `-devN` suffix in the add-on's
  `config.yaml` and the integration's `manifest.json` in lockstep
- `scripts/teardown-haos-vm.sh` — destroys the VM

## Versioning

Add-on and integration share a single version (B4). Format while developing
is `<semver>-dev<N>`, e.g. `2.0.0-dev7`. `./scripts/bump-dev-version.sh`
increments N and writes the new string into both
`outback_mate3_addon/config.yaml` and
`custom_components/outback_mate3/manifest.json`.

## Standing rule — always bump, push, and commit after each turn

After every turn that changes files in the repo:

1. **Bump the dev version**:

    ```sh
    ./scripts/bump-dev-version.sh
    ```

2. **Deploy** to the test VM so the bump + code changes are immediately
   visible (the bumped version shows on the add-on card and integration entry):

    ```sh
    ./scripts/install-addon.sh          # if outback_mate3_addon/ changed
    ./scripts/install-integration.sh    # if custom_components/outback_mate3/ changed
    scp scripts/provision-haos-vm.sh scripts/teardown-haos-vm.sh pve:/root/
                                        # if either of those two scripts changed
    ```

3. **Update the active task log**: for any tasks completed this turn,
   annotate with the current version — e.g. `- [x] B4 - ... _(2.0.0-dev3)_`.
   This is how we derive the changelog. The active log is `TASKS.md` at the
   repo root if one exists; otherwise use the most recent
   `archive/TASKS-*.md` (currently `archive/TASKS-2.0.0.md`).

4. **Commit** everything (the bump, the code changes, the task-log annotation)
   to the current branch (`weirded/ha-addon-plan`) with a clear message.

Do all four unless the user explicitly says not to. Changes the user can't
see sitting on my disk don't count as delivered.
