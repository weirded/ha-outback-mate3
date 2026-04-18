#!/usr/bin/env bash
#
# provision-haos-vm.sh
# Provision a Home Assistant OS VM on a Proxmox host for testing this project.
#
# Run this ON the Proxmox host (e.g. via `ssh pve ./provision-haos-vm.sh`).
# All settings are overrideable via environment variables; defaults match the
# choices made when this script was first written (3 GB RAM, 2 cores,
# sata-ssd storage, vmbr0 bridge).
#
# Example: VMID=107 VMNAME=haos-dev ./provision-haos-vm.sh
#
# Exit codes:
#   0  success
#   2  not running on a Proxmox host (`qm` missing)
#   3  VMID already in use
#   4  couldn't resolve HA OS download URL
#   5  disk import produced no `unused*` entry in VM config

set -euo pipefail

VMID="${VMID:-106}"
VMNAME="${VMNAME:-haos-test}"
STORAGE="${STORAGE:-sata-ssd}"
BRIDGE="${BRIDGE:-vmbr0}"
MEM_MB="${MEM_MB:-3072}"
CORES="${CORES:-2}"
DISK_SIZE_GB="${DISK_SIZE_GB:-32}"
HAOS_URL="${HAOS_URL:-}"
IMAGE_CACHE="${IMAGE_CACHE:-/var/lib/vz/template/iso}"
START_AFTER_PROVISION="${START_AFTER_PROVISION:-1}"

log() { printf '[%(%H:%M:%S)T] %s\n' -1 "$*" >&2; }

command -v qm >/dev/null || { echo "qm not found; run on a Proxmox host" >&2; exit 2; }

if qm status "$VMID" >/dev/null 2>&1; then
  echo "VMID $VMID already exists; pick another or destroy it first" >&2
  exit 3
fi

# --- Resolve + fetch the HA OS qcow2 image ---------------------------------

if [[ -z "$HAOS_URL" ]]; then
  log "Resolving latest HA OS release"
  HAOS_URL=$(
    curl -fsSL https://api.github.com/repos/home-assistant/operating-system/releases/latest \
      | grep -oE 'https://[^"]*haos_ova-[^"]*\.qcow2\.xz' \
      | head -1
  )
  [[ -n "$HAOS_URL" ]] || { echo "Couldn't resolve HA OS download URL; set HAOS_URL env var" >&2; exit 4; }
fi

COMPRESSED_NAME=$(basename "$HAOS_URL")
DECOMPRESSED_NAME="${COMPRESSED_NAME%.xz}"
IMAGE_PATH="$IMAGE_CACHE/$DECOMPRESSED_NAME"

mkdir -p "$IMAGE_CACHE"

if [[ ! -f "$IMAGE_PATH" ]]; then
  log "Downloading $HAOS_URL"
  curl -fL --progress-bar "$HAOS_URL" -o "$IMAGE_CACHE/$COMPRESSED_NAME"
  log "Decompressing"
  xz -d "$IMAGE_CACHE/$COMPRESSED_NAME"
else
  log "Reusing cached $IMAGE_PATH"
fi

# --- Safety net: if anything fails after VM creation, clean it up ---------

cleanup_on_error() {
  local rc=$?
  if (( rc != 0 )) && qm status "$VMID" >/dev/null 2>&1; then
    log "Error (rc=$rc); destroying partial VM $VMID"
    qm stop "$VMID" --skiplock 1 >/dev/null 2>&1 || true
    qm destroy "$VMID" --purge 1 --skiplock 1 >/dev/null 2>&1 || true
  fi
  exit $rc
}
trap cleanup_on_error ERR

# --- Create the VM shell ---------------------------------------------------

log "Creating VM $VMID ($VMNAME) on $STORAGE, ${MEM_MB}MB RAM, ${CORES} cores"
qm create "$VMID" \
  --name "$VMNAME" \
  --memory "$MEM_MB" \
  --cores "$CORES" \
  --net0 "virtio,bridge=$BRIDGE" \
  --ostype l26 \
  --machine q35 \
  --bios ovmf \
  --scsihw virtio-scsi-pci \
  --tablet 0 \
  --onboot 0

log "Adding EFI vars disk"
qm set "$VMID" --efidisk0 "${STORAGE}:1,efitype=4m,pre-enrolled-keys=1,format=raw"

# --- Import the HA OS disk -------------------------------------------------

log "Importing HA OS disk ($DECOMPRESSED_NAME) → $STORAGE"
qm importdisk "$VMID" "$IMAGE_PATH" "$STORAGE" --format raw

# The imported disk is added to the VM config as `unusedN: storage:volume`.
IMPORTED_LINE=$(qm config "$VMID" | grep -E '^unused[0-9]+:' | head -1 || true)
[[ -n "$IMPORTED_LINE" ]] || { echo "Disk import produced no unused* entry" >&2; exit 5; }
IMPORTED_KEY="${IMPORTED_LINE%%:*}"
IMPORTED_VOLUME="${IMPORTED_LINE#*: }"

log "Attaching $IMPORTED_VOLUME as scsi0"
# Must be two calls: if `--delete` runs in the same `qm set` as `--scsi0`,
# Proxmox processes --delete first and purges the underlying volume, leaving
# --scsi0 pointing at a volume that no longer exists.
qm set "$VMID" --scsi0 "${IMPORTED_VOLUME},discard=on,ssd=1"
qm set "$VMID" --delete "$IMPORTED_KEY"

log "Resizing disk to ${DISK_SIZE_GB}G"
qm resize "$VMID" scsi0 "${DISK_SIZE_GB}G"

log "Setting boot order to scsi0"
qm set "$VMID" --boot order=scsi0

# Don't run the cleanup trap if we reach this point.
trap - ERR

# --- Start (optional) ------------------------------------------------------

if [[ "$START_AFTER_PROVISION" == "1" ]]; then
  log "Starting VM $VMID"
  qm start "$VMID"
fi

cat >&2 <<EOF

Done.

VM $VMID ($VMNAME) created. Next steps:

  1. Open the Proxmox web UI → VM $VMID → Console to watch HA OS boot
     (first boot takes ~5 minutes; it downloads Supervisor).
  2. Once it says "Welcome to Home Assistant", visit http://homeassistant.local:8123
     (or the VM's DHCP-assigned IP on port 8123) and create your HA account.
  3. Add this repo as an add-on repository via
     Settings → Add-ons → Add-on Store → ⋮ → Repositories.

To start over:
  qm stop $VMID && qm destroy $VMID --purge

EOF
