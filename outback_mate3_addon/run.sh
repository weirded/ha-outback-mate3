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
#
# This is a *convenience only* — the UDP->WS relay below does not depend on it.
# The sync therefore runs in a separate script that is guarded so that ANY
# failure (permission denied on the target, files in use, read-only mount) is
# logged as a warning and does NOT stop the add-on from starting. Note the
# `|| rc=$?`: without it, `set -e` would abort the whole run script the moment
# the sync exits non-zero — which is exactly what crash-looped the add-on when
# the target dir was not removable.

BUNDLED="/opt/integration/outback_mate3"
TARGET="/homeassistant/custom_components/outback_mate3"

if [ -d /homeassistant ]; then
    rc=0
    /app/deploy_integration.sh "$BUNDLED" "$TARGET" || rc=$?
    case "$rc" in
        0)  bashio::log.warning "Integration was updated; restart Home Assistant to load the new version." ;;
        10) bashio::log.debug "Bundled integration already current at ${TARGET}" ;;
        2)  bashio::log.debug "No bundled integration in image; skipping auto-deploy." ;;
        *)  bashio::log.warning "Could not sync the bundled integration into ${TARGET} (rc=${rc}: permission denied, files in use, or read-only). The add-on will keep running — the relay does not depend on this. Update ${TARGET} manually or fix its permissions to re-enable auto-deploy." ;;
    esac
else
    bashio::log.warning "/homeassistant is not mapped — integration auto-deploy skipped. Add 'map: [homeassistant_config:rw]' to config.yaml to enable."
fi


cd /app
exec python3 -m src.main
