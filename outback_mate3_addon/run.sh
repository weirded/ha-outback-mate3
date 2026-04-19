#!/usr/bin/with-contenv bashio
set -e

UDP_PORT="$(bashio::config 'udp_port')"
WS_PORT="$(bashio::config 'ws_port')"
LOG_LEVEL="$(bashio::config 'log_level')"
MIN_UPDATE_INTERVAL_S="$(bashio::config 'min_update_interval_s')"
CONFIG_POLL_INTERVAL_S="$(bashio::config 'config_poll_interval_s')"
ADDON_VERSION="$(bashio::addon.version)"

export UDP_PORT WS_PORT LOG_LEVEL MIN_UPDATE_INTERVAL_S CONFIG_POLL_INTERVAL_S ADDON_VERSION

bashio::log.info "Outback MATE3 v${ADDON_VERSION}: UDP :${UDP_PORT} -> WS :${WS_PORT} (throttle ${MIN_UPDATE_INTERVAL_S}s, config poll ${CONFIG_POLL_INTERVAL_S}s, log ${LOG_LEVEL})"

# --- Deploy bundled integration into HA's config dir -----------------------
# B9: the add-on ships the companion integration in its image. On every start
# we sync it into /homeassistant/custom_components/outback_mate3/ if the
# content differs. That way users install ONE thing (this add-on) and the
# integration ends up in the right place; they just restart HA to load it.

BUNDLED="/opt/integration/outback_mate3"
TARGET="/homeassistant/custom_components/outback_mate3"

if [ -d "$BUNDLED" ]; then
    if [ -d /homeassistant ]; then
        mkdir -p /homeassistant/custom_components
        if ! diff -rq "$BUNDLED" "$TARGET" >/dev/null 2>&1; then
            bashio::log.info "Deploying bundled integration to ${TARGET}"
            rm -rf "$TARGET"
            cp -R "$BUNDLED" "$TARGET"
            bashio::log.warning "Integration was updated; restart Home Assistant to load the new version."
        else
            bashio::log.debug "Bundled integration already current at ${TARGET}"
        fi
    else
        bashio::log.warning "/homeassistant is not mapped — integration auto-deploy skipped. Add 'map: [homeassistant_config:rw]' to config.yaml to enable."
    fi
fi


cd /app
exec python3 -m src.main
