"""D5: Validate translation coverage against the add-on's advertised schema.

The add-on is the sole source of MATE3 protocol knowledge — translation
labels still live in the integration (HA store compliance requires it) but
the canonical *set* of labels is driven by what the add-on advertises:

* Every live / config `translation_key` must have a corresponding
  `entity.sensor.<key>.name` entry.
* Every enum option (inverter_mode, ac_mode, charge_mode, grid_mode) must
  have a corresponding `entity.sensor.<key>.state.<option>` entry — this
  prevents the parser from emitting a state string the integration has
  no label for.
* `strings.json` and `translations/en.json` must be byte-identical (en is
  the reference locale; HA stores the two files separately but we maintain
  them in lockstep).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "outback_mate3_addon"))

from src.config_schema import build_config_schema  # noqa: E402
from src.schema import build_live_schema  # noqa: E402

INTEGRATION_DIR = REPO_ROOT / "custom_components" / "outback_mate3"
STRINGS_FILE = INTEGRATION_DIR / "strings.json"
EN_FILE = INTEGRATION_DIR / "translations" / "en.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sensor_labels(doc: dict) -> dict[str, dict]:
    return doc.get("entity", {}).get("sensor", {})


def test_strings_and_en_are_identical():
    """Root locale and the en reference must not drift."""
    assert _load(STRINGS_FILE) == _load(EN_FILE)


def test_every_live_translation_key_has_a_name():
    sensors = _sensor_labels(_load(STRINGS_FILE))
    live = build_live_schema()
    missing = []
    for kind, specs in live.items():
        for spec in specs:
            tk = spec["translation_key"]
            if tk not in sensors:
                missing.append(f"{kind}.{tk}")
            elif "name" not in sensors[tk]:
                missing.append(f"{kind}.{tk} (no .name)")
    assert not missing, f"Live specs missing translation labels: {missing}"


def test_every_config_translation_key_has_a_name():
    sensors = _sensor_labels(_load(STRINGS_FILE))
    config = build_config_schema()
    missing = []
    for section, specs in config.items():
        for spec in specs:
            tk = spec["translation_key"]
            if tk not in sensors:
                missing.append(f"{section}.{tk}")
            elif "name" not in sensors[tk]:
                missing.append(f"{section}.{tk} (no .name)")
    assert not missing, f"Config specs missing translation labels: {missing}"


def test_enum_options_have_state_labels():
    """HA won't localize enum values without a `state` block. Any option the
    parser might emit must have a label, including the `unknown` fallback."""
    sensors = _sensor_labels(_load(STRINGS_FILE))
    live = build_live_schema()
    missing = []
    for kind, specs in live.items():
        for spec in specs:
            if spec["device_class"] != "enum":
                continue
            tk = spec["translation_key"]
            states = sensors.get(tk, {}).get("state", {})
            for opt in spec["options"] or ():
                if opt not in states:
                    missing.append(f"{kind}.{tk}.state.{opt}")
    assert not missing, f"Enum options missing state labels: {missing}"


def test_strings_does_not_label_keys_the_schema_no_longer_emits():
    """Dead labels bloat the UI translations bundle. A key in strings.json
    that's not in either schema is either a typo or leftover from a removed
    field — flag it so the label set stays tight."""
    sensors = _sensor_labels(_load(STRINGS_FILE))
    live_keys = {s["translation_key"] for specs in build_live_schema().values() for s in specs}
    config_keys = {s["translation_key"] for specs in build_config_schema().values() for s in specs}
    # System aggregates are integration-side rollups not in the schema; allow-list them.
    allowlist = {
        "from_grid",
        "solar_production",
        "from_battery",
        "to_loads",
        "battery_voltage",
        "solar_production_energy",
    }
    advertised = live_keys | config_keys | allowlist
    extra = set(sensors.keys()) - advertised
    assert not extra, f"strings.json has labels not advertised by any schema: {sorted(extra)}"
