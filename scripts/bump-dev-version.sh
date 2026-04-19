#!/usr/bin/env bash
#
# bump-dev-version.sh
# Increment the shared development version across the add-on and integration.
#
# Format: `<semver>-dev<N>`, e.g. `2.0.0-dev3`. Both
# outback_mate3_addon/config.yaml (add-on `version`) and
# custom_components/outback_mate3/manifest.json (integration `version`) are
# updated in lockstep so a running system's two pieces always advertise the
# same version string.
#
# Behaviour:
#   - If current version is `X.Y.Z-devN`, bumps to `X.Y.Z-dev(N+1)`.
#   - If current version has no `-dev` suffix, initializes to `X.Y.Z-dev1`.
#
# Usage:
#   ./scripts/bump-dev-version.sh              # auto-bump
#   ./scripts/bump-dev-version.sh 2.0.0-dev5   # set explicitly (for releases)

set -euo pipefail

CONFIG_YAML="outback_mate3_addon/config.yaml"
MANIFEST_JSON="custom_components/outback_mate3/manifest.json"

[[ -f "$CONFIG_YAML" ]] || { echo "$CONFIG_YAML not found (run from repo root)" >&2; exit 1; }
[[ -f "$MANIFEST_JSON" ]] || { echo "$MANIFEST_JSON not found (run from repo root)" >&2; exit 1; }

if [[ $# -ge 1 ]]; then
  NEW="$1"
else
  CURRENT=$(awk -F'"' '/^version:/ {print $2; exit}' "$CONFIG_YAML")
  if [[ "$CURRENT" =~ ^(.+)-dev([0-9]+)$ ]]; then
    NEW="${BASH_REMATCH[1]}-dev$((BASH_REMATCH[2] + 1))"
  elif [[ -n "$CURRENT" ]]; then
    NEW="${CURRENT}-dev1"
  else
    echo "Couldn't parse version from $CONFIG_YAML" >&2
    exit 2
  fi
fi

# Update add-on config.yaml
python3 - "$CONFIG_YAML" "$NEW" <<'PY'
import re, sys
path, new = sys.argv[1:]
txt = open(path).read()
txt = re.sub(r'^version:\s*"[^"]*"', f'version: "{new}"', txt, count=1, flags=re.MULTILINE)
open(path, "w").write(txt)
PY

# Update integration manifest.json (preserve formatting)
python3 - "$MANIFEST_JSON" "$NEW" <<'PY'
import json, sys
path, new = sys.argv[1:]
d = json.load(open(path))
d["version"] = new
with open(path, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
PY

echo "$NEW"
