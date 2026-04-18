#!/usr/bin/env bash
#
# provision-haos-vm.sh
# Provision a Home Assistant OS VM on a Proxmox host, non-interactively.
#
# The `qm` invocation mirrors the community-maintained installer at
#   https://community-scripts.github.io/ProxmoxVE/scripts?id=haos-vm
# (github.com/community-scripts/ProxmoxVE vm/haos-vm.sh), minus the whiptail
# UI. Their choices were battle-tested; the only thing we change is keeping
# it scriptable by driving every parameter from env vars / defaults.
#
# Run this ON the Proxmox host (e.g. `ssh pve bash /root/provision-haos-vm.sh`).
# All settings override via environment.
#
# Exit codes:
#   0  success
#   2  not a Proxmox host (qm missing)
#   3  VMID already in use
#   4  couldn't resolve HA OS version
#   5  disk import produced no reference

set -euo pipefail

VMID="${VMID:-106}"
VMNAME="${VMNAME:-haos-test}"
STORAGE="${STORAGE:-sata-ssd}"
BRIDGE="${BRIDGE:-vmbr0}"
MEM_MB="${MEM_MB:-3072}"
CORES="${CORES:-2}"
DISK_SIZE="${DISK_SIZE:-32G}"
HAOS_VERSION="${HAOS_VERSION:-}"
IMAGE_CACHE="${IMAGE_CACHE:-/var/lib/vz/template/iso}"
START_AFTER_PROVISION="${START_AFTER_PROVISION:-1}"

log() { printf '[%(%H:%M:%S)T] %s\n' -1 "$*" >&2; }

command -v qm >/dev/null || { echo "qm not found; run on a Proxmox host" >&2; exit 2; }

if qm status "$VMID" >/dev/null 2>&1; then
  echo "VMID $VMID already exists; pick another VMID or destroy it first." >&2
  exit 3
fi

# --- Resolve HA OS version + URL ------------------------------------------

if [[ -z "$HAOS_VERSION" ]]; then
  log "Resolving latest stable HA OS version"
  HAOS_VERSION=$(
    curl -fsSL https://raw.githubusercontent.com/home-assistant/version/master/stable.json \
      | grep '"ova"' | cut -d '"' -f 4
  )
  [[ -n "$HAOS_VERSION" ]] || { echo "Couldn't resolve HA OS version" >&2; exit 4; }
fi
HAOS_URL="https://github.com/home-assistant/operating-system/releases/download/${HAOS_VERSION}/haos_ova-${HAOS_VERSION}.qcow2.xz"
COMPRESSED_NAME="haos_ova-${HAOS_VERSION}.qcow2.xz"
DECOMPRESSED_NAME="haos_ova-${HAOS_VERSION}.qcow2"
IMAGE_PATH="${IMAGE_CACHE}/${DECOMPRESSED_NAME}"

mkdir -p "$IMAGE_CACHE"

if [[ ! -f "$IMAGE_PATH" ]]; then
  log "Downloading $HAOS_URL"
  curl -fL --progress-bar "$HAOS_URL" -o "${IMAGE_CACHE}/${COMPRESSED_NAME}"
  log "Decompressing"
  xz -d "${IMAGE_CACHE}/${COMPRESSED_NAME}"
else
  log "Reusing cached $IMAGE_PATH"
fi

# --- Safety net: clean up partial VM on error ------------------------------

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

# --- Create VM shell -------------------------------------------------------

log "Creating VM $VMID ($VMNAME) on $STORAGE, ${MEM_MB}MB RAM, ${CORES} cores, HAOS $HAOS_VERSION"
qm create "$VMID" \
  -machine q35 \
  -bios ovmf \
  -tablet 0 \
  -localtime 1 \
  -agent 1 \
  -cores "$CORES" \
  -memory "$MEM_MB" \
  -name "$VMNAME" \
  -tags "ha-outback-mate3,test" \
  -net0 "virtio,bridge=${BRIDGE}" \
  -onboot 0 \
  -ostype l26 \
  -scsihw virtio-scsi-pci \
  -serial0 socket

# --- Import the HAOS disk --------------------------------------------------

log "Importing HA OS disk → $STORAGE"
# Prefer modern `qm disk import` where available, fall back to legacy.
if qm disk import --help >/dev/null 2>&1; then
  IMPORT_CMD=(qm disk import)
else
  IMPORT_CMD=(qm importdisk)
fi
IMPORT_OUT="$("${IMPORT_CMD[@]}" "$VMID" "$IMAGE_PATH" "$STORAGE" --format raw 2>&1 || true)"
DISK_REF="$(printf '%s\n' "$IMPORT_OUT" \
  | sed -n "s/.*successfully imported disk '\([^']\+\)'.*/\1/p" \
  | tr -d "\r\"'")"
if [[ -z "$DISK_REF" ]]; then
  # Fallback: find the disk in storage by VMID
  DISK_REF="$(pvesm list "$STORAGE" \
    | awk -v id="$VMID" '$5 ~ ("vm-"id"-disk-") {print $1":"$5}' \
    | sort | tail -n1)"
fi
if [[ -z "$DISK_REF" ]]; then
  echo "Unable to determine imported disk reference." >&2
  echo "$IMPORT_OUT" >&2
  exit 5
fi
log "Imported: $DISK_REF"

# --- Attach EFI vars disk + root disk in a single qm set ------------------
# NOTE: pre-enrolled-keys is intentionally NOT set. Enabling it turns on
# Secure Boot with Microsoft-signed keys; HA OS isn't signed with those and
# the firmware rejects the boot volume with "Access Denied".

log "Attaching EFI vars + root disk, setting boot order"
qm set "$VMID" \
  --efidisk0 "${STORAGE}:0,efitype=4m" \
  --scsi0 "${DISK_REF},ssd=1,discard=on" \
  --boot order=scsi0

log "Resizing root disk to ${DISK_SIZE}"
qm resize "$VMID" scsi0 "${DISK_SIZE}"

trap - ERR

if [[ "$START_AFTER_PROVISION" == "1" ]]; then
  log "Starting VM $VMID"
  qm start "$VMID"
fi

cat >&2 <<EOF

Done. VM $VMID ($VMNAME) created.

  - Proxmox web UI:  VM $VMID → Console   (first boot takes ~5 min)
  - Home Assistant:  http://homeassistant.local:8123 once booted
  - Add this repo as an add-on repository via Settings → Add-ons → ⋮ → Repositories

Start over with:   qm stop $VMID && qm destroy $VMID --purge

EOF
