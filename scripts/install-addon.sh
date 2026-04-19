#!/usr/bin/env bash
#
# install-addon.sh
# Deploy the local outback_mate3_addon/ source into a HAOS test VM, then
# install (or rebuild) the add-on via Supervisor. Ensures it ends up running.
#
# Fast dev loop: edit locally → run this → add-on is live in the test HA.
# No git push, no Samba share, no SSH add-on — files go straight into the
# VM through Proxmox's qemu-guest-agent file-write / exec RPCs, and all
# Supervisor operations are driven by `ha` CLI calls via `docker exec` on
# the guest. Consequence: no Home Assistant long-lived token is needed
# for this script (Supervisor trusts the host).
#
# Prerequisites:
#   - Test VM provisioned (scripts/provision-haos-vm.sh) with -agent 1
#   - SSH access to the Proxmox host, which can run `pvesh`
#
# Usage:
#   ./scripts/install-addon.sh
#
# Env overrides:
#   PVE_HOST   (default pve)
#   VMID       (default 106)
#   ADDON_SLUG (default outback_mate3)
#   ADDON_DIR  (default outback_mate3_addon)

set -euo pipefail

PVE_HOST="${PVE_HOST:-pve}"
VMID="${VMID:-106}"
ADDON_SLUG="${ADDON_SLUG:-outback_mate3}"
ADDON_DIR="${ADDON_DIR:-outback_mate3_addon}"

FULL_SLUG="local_${ADDON_SLUG}"
GUEST_TAR="/tmp/${ADDON_SLUG}.tar"
GUEST_TARGET="/mnt/data/supervisor/addons/local/${ADDON_SLUG}"

[[ -d "$ADDON_DIR" ]] || { echo "Add-on source dir $ADDON_DIR not found (run from repo root)" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 required locally (for parsing pvesh JSON)" >&2; exit 2; }

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

# Run a command on the Proxmox host and print stdout
pve() { ssh "$PVE_HOST" "$@"; }

# Run a shell command inside the HAOS guest via qemu-guest-agent and wait
# for completion. Prints stdout on 1, stderr on 2; returns the guest exit
# code. The script is uploaded to pve as a file (avoids escaping issues),
# then pve drives guest-exec and polls exec-status until done.
guest_exec() {
  local script="$1"
  local timeout_s="${2:-600}"

  # Upload the script text to a temp file on pve.
  local remote_script
  remote_script=$(ssh "$PVE_HOST" mktemp -t guest_exec.XXXXXX)
  printf '%s' "$script" | ssh "$PVE_HOST" "cat > $remote_script"

  # Orchestrator runs on pve: reads the script, fires guest-exec, polls.
  ssh "$PVE_HOST" "VMID=$VMID TIMEOUT_S=$timeout_s SCRIPT_FILE=$remote_script bash -s" <<'REMOTE'
set -euo pipefail
TMPJSON=$(mktemp)
trap 'rm -f "$TMPJSON" "$SCRIPT_FILE"' EXIT

SCRIPT=$(cat "$SCRIPT_FILE")
pvesh create "/nodes/pve/qemu/$VMID/agent/exec" \
  --command /bin/sh --command -c --command "$SCRIPT" \
  --output-format json > "$TMPJSON"
PID=$(python3 -c "import sys,json; print(json.load(open(sys.argv[1]))['pid'])" "$TMPJSON")

for _ in $(seq 1 "$TIMEOUT_S"); do
  pvesh get "/nodes/pve/qemu/$VMID/agent/exec-status" \
    --pid "$PID" --output-format json > "$TMPJSON"
  if python3 -c "import sys,json; sys.exit(0 if json.load(open(sys.argv[1])).get('exited') else 1)" "$TMPJSON"; then
    python3 - "$TMPJSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if d.get("out-data"):
    sys.stdout.write(d["out-data"])
if d.get("err-data"):
    sys.stderr.write(d["err-data"])
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

# Convenience: run ha CLI inside the VM. Default 60s timeout; installs and
# rebuilds can take several minutes on first build, so callers override.
ha_cli() {
  local timeout="${HA_CLI_TIMEOUT:-60}"
  guest_exec "docker exec hassio_cli ha $*" "$timeout"
}

# --- 1. Build tarball (exclude macOS AppleDouble metadata) ---------------

log "Syncing bundled integration into add-on dir"
./scripts/sync-bundled-integration.sh >/dev/null

log "Packaging $ADDON_DIR"
TARBALL=$(mktemp -t outback_mate3_addon.XXXXXX).tar
trap 'rm -f "$TARBALL"' EXIT
# macOS tar writes ._* AppleDouble entries for files with extended attrs;
# they confuse Supervisor's store scanner. COPYFILE_DISABLE=1 is the documented
# environment-variable way to suppress that on bsdtar / macOS tar.
COPYFILE_DISABLE=1 tar cf "$TARBALL" -C "$ADDON_DIR" \
  --exclude="__pycache__" --exclude=".pytest_cache" --exclude="tests" \
  --exclude="._*" \
  .
log "Tarball size: $(du -h "$TARBALL" | awk '{print $1}')"

# --- 2. Push to guest in chunks (pvesh --content capped at 60 KB) --------

log "Copying tarball to $PVE_HOST"
REMOTE_STAGE="/tmp/outback_mate3_addon-$$.tar"
scp -q "$TARBALL" "$PVE_HOST:$REMOTE_STAGE"

log "Pushing tarball to VM $VMID via qga file-write (chunked)"
ssh "$PVE_HOST" bash -s "$VMID" "$REMOTE_STAGE" <<'REMOTE'
set -euo pipefail
VMID="$1"
SRC="$2"
CHUNK_DIR=$(mktemp -d)
trap 'rm -rf "$CHUNK_DIR" "$SRC"' EXIT
split -b 40000 -a 3 -d "$SRC" "$CHUNK_DIR/c."
for f in "$CHUNK_DIR"/c.*; do
  name=$(basename "$f")
  B64=$(base64 -w0 < "$f")
  pvesh create "/nodes/pve/qemu/$VMID/agent/file-write" \
    --encode 0 --file "/tmp/$name" --content "$B64" >/dev/null
done
REMOTE

# --- 3. Reassemble + extract on the guest --------------------------------

log "Extracting into $GUEST_TARGET"
guest_exec "
set -e
cat /tmp/c.* > $GUEST_TAR
rm -f /tmp/c.*
rm -rf $GUEST_TARGET
mkdir -p $GUEST_TARGET
cd $GUEST_TARGET
tar xf $GUEST_TAR
rm -f $GUEST_TAR
" >/dev/null

# --- 4. Install or rebuild via Supervisor CLI ----------------------------

log "Reloading Supervisor store"
ha_cli "store reload --no-progress" >/dev/null 2>&1 \
  || ha_cli "store reload" >/dev/null 2>&1 || true

# Check if already installed: `ha apps info <slug>` exits 0 if installed
INFO_JSON=$(ha_cli "apps info $FULL_SLUG --raw-json" 2>/dev/null || echo '{"data":{}}')
# `installed` is the authoritative flag; `version` is null on a not-yet-
# installed store app (which `read` with a default IFS would mis-split).
INSTALLED=$(python3 -c "import sys,json; print('1' if json.loads(sys.stdin.read()).get('data',{}).get('installed') else '0')" <<<"$INFO_JSON")
INSTALLED_VERSION=$(python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('data',{}).get('version') or '')" <<<"$INFO_JSON")
LATEST_VERSION=$(python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('data',{}).get('version_latest') or '')" <<<"$INFO_JSON")

if [[ "$INSTALLED" != "1" ]]; then
  log "Installing $FULL_SLUG (first build can take several minutes)"
  HA_CLI_TIMEOUT=900 ha_cli "apps install $FULL_SLUG" >/dev/null
elif [[ "$INSTALLED_VERSION" != "$LATEST_VERSION" ]]; then
  # Supervisor refuses `apps rebuild` when the version changed in config.yaml;
  # use `apps update` to pick up the new version + build.
  log "Updating $FULL_SLUG ($INSTALLED_VERSION → $LATEST_VERSION)"
  HA_CLI_TIMEOUT=900 ha_cli "apps update $FULL_SLUG" >/dev/null
else
  log "Rebuilding $FULL_SLUG (was at $INSTALLED_VERSION, same version — code-only change)"
  HA_CLI_TIMEOUT=900 ha_cli "apps rebuild $FULL_SLUG" >/dev/null
fi

log "Ensuring $FULL_SLUG is running"
# `apps restart` starts a stopped add-on AND restarts a running one — safe either way.
ha_cli "apps restart $FULL_SLUG" >/dev/null

# --- 5. Report --------------------------------------------------------------

log "Verifying add-on state"
STATE_JSON=$(ha_cli "apps info $FULL_SLUG --raw-json" 2>/dev/null || echo '{}')
VERSION=$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()).get('data',{}); print(d.get('version','?'))" <<<"$STATE_JSON")
STATE=$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()).get('data',{}); print(d.get('state','?'))" <<<"$STATE_JSON")

cat >&2 <<EOF

Add-on '$FULL_SLUG' is installed (version $VERSION, state $STATE).

Tail logs:
  ssh $PVE_HOST 'docker exec hassio_cli ha apps logs $FULL_SLUG'

WebSocket URL for the integration:
  ws://<ha-host-or-ip>:28099/ws

EOF
