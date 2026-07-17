#!/usr/bin/env bash
# Sync the bundled companion integration into Home Assistant's
# custom_components dir (B9 — users install ONE thing, the add-on, and the
# integration lands automatically).
#
# This is a *convenience*: the add-on's core job — relaying MATE3 UDP telemetry
# to WebSocket — does NOT depend on it. So this script is deliberately isolated
# from run.sh and NEVER aborts the add-on: run.sh invokes it guarded and treats
# any failure as a warning, not a fatal error. A non-writable, in-use, or
# read-only target (seen in the wild when the files are owned by another uid,
# e.g. a manual copy) must not crash-loop the relay.
#
# Usage:  deploy_integration.sh <bundled_dir> <target_dir>
# Exit codes (consumed by run.sh):
#    0  updated — caller should tell the user to restart Home Assistant
#   10  already current — nothing to do
#    2  no bundled integration in the image — nothing to do
#    3  target's parent dir could not be created
#    5  existing target could not be removed (permission denied / in use)
#    6  bundled integration could not be copied into place
set -u

BUNDLED="${1:?bundled integration dir required}"
TARGET="${2:?target dir required}"

# Nothing shipped in the image → nothing to deploy.
[ -d "$BUNDLED" ] || exit 2

# Ensure the parent exists (mkdir -p is a no-op success if it already does,
# even when we lack write permission on it).
mkdir -p "$(dirname "$TARGET")" 2>/dev/null || exit 3

# Already in sync → no destructive work needed.
if diff -rq "$BUNDLED" "$TARGET" >/dev/null 2>&1; then
    exit 10
fi

# Replace the target. rm first (matches historical behaviour); if we cannot
# remove it we bail WITHOUT having touched anything, so the existing copy is
# left intact for the user to update by hand.
rm -rf "$TARGET" 2>/dev/null || exit 5
cp -R "$BUNDLED" "$TARGET" 2>/dev/null || exit 6

exit 0
