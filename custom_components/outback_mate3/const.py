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
