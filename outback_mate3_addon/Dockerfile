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

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import socket, sys; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1', 28099)); s.close()" || exit 1

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
