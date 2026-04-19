ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BUILD_VERSION

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

# Ship a copy of the companion integration inside the image so the add-on
# can deploy it into /homeassistant/custom_components/ at startup (B9).
# Users then only have to install the add-on — the integration lands
# automatically on the next HA restart.
COPY bundled_integration/outback_mate3/ /opt/integration/outback_mate3/

# s6-overlay expects a service under /etc/services.d/<name>/run; the HA base
# image's /init then supervises it. Don't set CMD — let the base image's
# default init run.
COPY run.sh /etc/services.d/outback_mate3/run
RUN chmod a+x /etc/services.d/outback_mate3/run

# No HEALTHCHECK: the WS port is user-configurable (ws_port option), so a
# fixed-port probe would falsely report unhealthy whenever the user retargets
# the port. Supervisor relies on s6-overlay supervising the service and
# restarting the container if /init exits, which is a stronger signal than
# a port poke anyway.

LABEL \
  io.hass.name="Outback MATE3" \
  io.hass.description="Relays Outback MATE3 UDP telemetry to Home Assistant over a structured WebSocket." \
  io.hass.arch="${BUILD_ARCH}" \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  maintainer="Stefan Zier <stefan@zier.com>" \
  org.opencontainers.image.title="Outback MATE3" \
  org.opencontainers.image.source="https://github.com/weirded/ha-outback-mate3" \
  org.opencontainers.image.licenses="MIT" \
  org.opencontainers.image.vendor="weirded"
