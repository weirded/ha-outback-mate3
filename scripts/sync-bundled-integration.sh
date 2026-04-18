#!/usr/bin/env bash
#
# sync-bundled-integration.sh
# Mirror custom_components/outback_mate3/ into
# outback_mate3_addon/bundled_integration/outback_mate3/ so the add-on's
# Docker build context has its own copy to deploy into /config on startup
# (B9). Both locations are committed; this script keeps them byte-identical.
#
# install-addon.sh calls this automatically before packaging; call it
# manually after editing the integration if you want to commit the bundled
# copy.

set -euo pipefail

SRC="custom_components/outback_mate3"
DST="outback_mate3_addon/bundled_integration/outback_mate3"

[[ -d "$SRC" ]] || { echo "$SRC not found (run from repo root)" >&2; exit 1; }
mkdir -p "$(dirname "$DST")"
rm -rf "$DST"
cp -R "$SRC" "$DST"
find "$DST" -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo "Synced $SRC → $DST"
