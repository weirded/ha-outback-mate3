#!/usr/bin/env bash
#
# teardown-haos-vm.sh
# Stop and destroy a Home Assistant OS VM created by provision-haos-vm.sh.
# Intended for development / test VMs only.
#
# Leaves the cached qcow2 image in /var/lib/vz/template/iso/ so the next
# provision run is fast. Remove manually if you want the disk back:
#   ssh pve 'rm /var/lib/vz/template/iso/haos_ova-*.qcow2'
#
# Usage:
#   ./scripts/teardown-haos-vm.sh pve              # interactive, VMID=106
#   VMID=107 ./scripts/teardown-haos-vm.sh pve     # different VMID
#   FORCE=1 ./scripts/teardown-haos-vm.sh pve      # no confirmation
#
# If $1 is omitted, the script assumes it's running ON the Proxmox host.

set -euo pipefail

VMID="${VMID:-106}"
FORCE="${FORCE:-0}"
PVE_HOST="${1:-}"

run_pve() {
  if [[ -n "$PVE_HOST" ]]; then
    ssh "$PVE_HOST" "$@"
  else
    bash -c "$*"
  fi
}

# Check that the VM exists; if it doesn't, we're already done.
if ! run_pve "qm status $VMID >/dev/null 2>&1"; then
  echo "VM $VMID does not exist${PVE_HOST:+ on $PVE_HOST}. Nothing to do." >&2
  exit 0
fi

STATUS=$(run_pve "qm config $VMID 2>/dev/null | grep -E '^(name|memory|scsi0):' | head -5")
echo "About to destroy VM $VMID${PVE_HOST:+ on $PVE_HOST}:" >&2
echo "$STATUS" | sed 's/^/  /' >&2

if [[ "$FORCE" != "1" ]]; then
  read -r -p "Type the VMID ($VMID) to confirm destruction: " ack
  if [[ "$ack" != "$VMID" ]]; then
    echo "Aborted." >&2
    exit 1
  fi
fi

run_pve "qm stop $VMID --skiplock 1 >/dev/null 2>&1 || true"
run_pve "qm destroy $VMID --purge 1 --skiplock 1"
echo "Destroyed VM $VMID." >&2
