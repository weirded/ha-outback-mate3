#!/usr/bin/env bash
#
# install-integration.sh
# Push the local custom_components/outback_mate3/ into the HAOS test VM and
# restart Home Assistant so the new code is loaded.
#
# Same file-transfer mechanism as install-addon.sh: tar → scp to pve →
# chunked pvesh file-write → guest tar-extract into
# /mnt/data/supervisor/homeassistant/custom_components/outback_mate3/.
#
# Prerequisites:
#   - Test VM provisioned (scripts/provision-haos-vm.sh) with -agent 1
#   - SSH access to the Proxmox host, which can run `pvesh`
#
# Usage:
#   ./scripts/install-integration.sh
#
# Env overrides:
#   PVE_HOST       (default pve)
#   VMID           (default 106)
#   INTEGRATION_DIR  (default custom_components/outback_mate3)
#   SKIP_RESTART   (default 0 — set 1 to skip the ha core restart)

set -euo pipefail

PVE_HOST="${PVE_HOST:-pve}"
VMID="${VMID:-106}"
INTEGRATION_DIR="${INTEGRATION_DIR:-custom_components/outback_mate3}"
SKIP_RESTART="${SKIP_RESTART:-0}"
# Proxmox cluster node name used in pvesh API paths (/nodes/<node>/...).
# Defaults match the single-host `pve` install; override PVE_NODE explicitly
# for clusters, or leave empty to auto-detect from `pvesh get /nodes`.
PVE_NODE="${PVE_NODE:-}"

if [[ -z "$PVE_NODE" ]]; then
  PVE_NODE=$(ssh "$PVE_HOST" "pvesh get /nodes --output-format json" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['node'])" 2>/dev/null) \
    || { echo "Couldn't auto-detect PVE_NODE; set PVE_NODE explicitly" >&2; exit 3; }
fi

INTEGRATION_NAME="$(basename "$INTEGRATION_DIR")"
INTEGRATION_PARENT="$(dirname "$INTEGRATION_DIR")"
GUEST_TAR="/tmp/${INTEGRATION_NAME}_integration.tar"
GUEST_TARGET="/mnt/data/supervisor/homeassistant/custom_components/${INTEGRATION_NAME}"

[[ -d "$INTEGRATION_DIR" ]] || { echo "$INTEGRATION_DIR not found (run from repo root)" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 required locally" >&2; exit 2; }

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

# Same guest_exec pattern as install-addon.sh.
guest_exec() {
  local script="$1"
  local timeout_s="${2:-120}"
  local remote_script
  remote_script=$(ssh "$PVE_HOST" mktemp -t guest_exec.XXXXXX)
  printf '%s' "$script" | ssh "$PVE_HOST" "cat > $remote_script"
  ssh "$PVE_HOST" "PVE_NODE=$PVE_NODE VMID=$VMID TIMEOUT_S=$timeout_s SCRIPT_FILE=$remote_script bash -s" <<'REMOTE'
set -euo pipefail
TMPJSON=$(mktemp)
trap 'rm -f "$TMPJSON" "$SCRIPT_FILE"' EXIT
SCRIPT=$(cat "$SCRIPT_FILE")
pvesh create "/nodes/$PVE_NODE/qemu/$VMID/agent/exec" \
  --command /bin/sh --command -c --command "$SCRIPT" \
  --output-format json > "$TMPJSON"
PID=$(python3 -c "import sys,json; print(json.load(open(sys.argv[1]))['pid'])" "$TMPJSON")
for _ in $(seq 1 "$TIMEOUT_S"); do
  pvesh get "/nodes/$PVE_NODE/qemu/$VMID/agent/exec-status" \
    --pid "$PID" --output-format json > "$TMPJSON"
  if python3 -c "import sys,json; sys.exit(0 if json.load(open(sys.argv[1])).get('exited') else 1)" "$TMPJSON"; then
    python3 - "$TMPJSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if d.get("out-data"): sys.stdout.write(d["out-data"])
if d.get("err-data"): sys.stderr.write(d["err-data"])
sys.exit(d.get("exitcode", 0))
PY
    exit $?
  fi
  sleep 1
done
echo "guest exec timed out after ${TIMEOUT_S}s" >&2
exit 124
REMOTE
}

# --- 1. Tarball the integration directory -------------------------------

log "Packaging $INTEGRATION_DIR"
TARBALL=$(mktemp -t outback_integration.XXXXXX).tar
trap 'rm -f "$TARBALL"' EXIT
COPYFILE_DISABLE=1 tar cf "$TARBALL" -C "$INTEGRATION_PARENT" \
  --exclude="__pycache__" --exclude=".pytest_cache" --exclude="._*" \
  "$INTEGRATION_NAME"
log "Tarball size: $(du -h "$TARBALL" | awk '{print $1}')"

# --- 2. Push chunked to the guest via qga -------------------------------

log "Copying tarball to $PVE_HOST"
REMOTE_STAGE="/tmp/outback_integration-$$.tar"
scp -q "$TARBALL" "$PVE_HOST:$REMOTE_STAGE"

log "Pushing tarball to VM $VMID via qga file-write (chunked)"
ssh "$PVE_HOST" bash -s "$PVE_NODE" "$VMID" "$REMOTE_STAGE" <<'REMOTE'
set -euo pipefail
PVE_NODE="$1"
VMID="$2"
SRC="$3"
CHUNK_DIR=$(mktemp -d)
trap 'rm -rf "$CHUNK_DIR" "$SRC"' EXIT
split -b 40000 -a 3 -d "$SRC" "$CHUNK_DIR/c."
for f in "$CHUNK_DIR"/c.*; do
  name=$(basename "$f")
  B64=$(base64 -w0 < "$f")
  pvesh create "/nodes/$PVE_NODE/qemu/$VMID/agent/file-write" \
    --encode 0 --file "/tmp/$name" --content "$B64" >/dev/null
done
REMOTE

# --- 3. Reassemble and extract on guest ---------------------------------

log "Extracting into $GUEST_TARGET"
guest_exec "
set -e
cat /tmp/c.* > $GUEST_TAR
rm -f /tmp/c.*
mkdir -p $(dirname "$GUEST_TARGET")
rm -rf $GUEST_TARGET
cd $(dirname "$GUEST_TARGET")
tar xf $GUEST_TAR
rm -f $GUEST_TAR
" >/dev/null

# --- 4. Restart HA core so new code is loaded ---------------------------

if [[ "$SKIP_RESTART" == "1" ]]; then
  log "SKIP_RESTART=1; integration files in place but HA not restarted"
else
  log "Restarting HA core (takes ~30s to become responsive again)"
  guest_exec "docker exec hassio_cli ha core restart" 60 >/dev/null
fi

log "Done: integration deployed to VM $VMID"
