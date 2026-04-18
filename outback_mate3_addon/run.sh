#!/usr/bin/with-contenv bashio
set -e

UDP_PORT="$(bashio::config 'udp_port')"
WS_PORT="$(bashio::config 'ws_port')"
LOG_LEVEL="$(bashio::config 'log_level')"
MIN_UPDATE_INTERVAL_S="$(bashio::config 'min_update_interval_s')"
CONFIG_POLL_INTERVAL_S="$(bashio::config 'config_poll_interval_s')"

export UDP_PORT WS_PORT LOG_LEVEL MIN_UPDATE_INTERVAL_S CONFIG_POLL_INTERVAL_S

bashio::log.info "Outback MATE3: UDP :${UDP_PORT} -> WS :${WS_PORT} (throttle ${MIN_UPDATE_INTERVAL_S}s, config poll ${CONFIG_POLL_INTERVAL_S}s, log ${LOG_LEVEL})"

cd /app
exec python3 -m src.main
