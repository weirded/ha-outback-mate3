#!/usr/bin/env bash
#
# provision-haos-vm.sh
#
# Launch the community-maintained Home Assistant OS VM installer on a
# Proxmox host to get a clean test VM for this project.
#
# Source: https://community-scripts.github.io/ProxmoxVE/scripts?id=haos-vm
# Script: https://github.com/community-scripts/ProxmoxVE/raw/main/vm/haos-vm.sh
#
# The installer is interactive (whiptail). When it asks "Use Default
# Settings?", pick **Advanced** and enter the answers documented below to
# match the choices used for this project's test VM. You can also accept
# the defaults if this is a fresh Proxmox host with plenty of room.
#
# ------------------------------------------------------------------------
# Suggested answers for this project on a host like `pve`:
#   Version             : stable
#   Virtual Machine ID  : any free ID (installer picks one)
#   Machine Type        : q35
#   Disk Cache          : default
#   Hostname            : haos-test
#   CPU Model           : KVM64 (or 'host' if you want full feature set)
#   CPU Cores           : 2
#   RAM Size            : 3072  (bump to 4096 if the host has spare)
#   Storage             : sata-ssd   <-- matches our pve setup
#   Bridge              : vmbr0
#   MAC Address         : (auto)
#   VLAN                : (none)
#   MTU                 : (default)
#   Start VM on boot    : yes
# ------------------------------------------------------------------------
#
# Usage:
#   ./scripts/provision-haos-vm.sh pve
#
# The first argument is the Proxmox host to SSH into. If omitted, runs
# directly against the local machine (i.e. if you're already on the
# Proxmox host).

set -euo pipefail

readonly SCRIPT_URL="https://github.com/community-scripts/ProxmoxVE/raw/main/vm/haos-vm.sh"
readonly INSTALLER='bash -c "$(curl -fsSL '"$SCRIPT_URL"')"'

PVE_HOST="${1:-}"

if [[ -n "$PVE_HOST" ]]; then
  # Force a pseudo-TTY so whiptail renders properly over SSH.
  exec ssh -t "$PVE_HOST" "$INSTALLER"
else
  # Already on the Proxmox host.
  exec bash -c "$(curl -fsSL "$SCRIPT_URL")"
fi
