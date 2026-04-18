ARG BUILD_FROM
FROM $BUILD_FROM

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
