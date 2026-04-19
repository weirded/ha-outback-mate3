"""Constants for the Outback MATE3 integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "outback_mate3"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_URL = "url"
DEFAULT_URL = "ws://local-outback-mate3:28099/ws"

KIND_INVERTER = "inverter"
KIND_CHARGE_CONTROLLER = "charge_controller"

# WebSocket connection tuning.
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
WS_HEARTBEAT_S = 30.0

# `binary_sensor.mate3_system_receiving_data` — connectivity indicator.
STALE_AFTER_S = 300.0
CONNECTIVITY_POLL_INTERVAL = timedelta(seconds=30)

# Repairs issue IDs.
ISSUE_ADDON_OFFLINE = "addon_offline"
ISSUE_VERSION_DRIFT = "version_drift"

# How long the add-on may be unreachable before we create the `addon_offline`
# Repairs issue. Keeps short Supervisor restarts / network hiccups from
# opening (and immediately re-closing) a Repair every reconnect cycle.
ADDON_OFFLINE_GRACE_S = 60.0
