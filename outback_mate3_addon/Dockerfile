ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

# s6-overlay expects a service under /etc/services.d/<name>/run; the HA base
# image's /init then supervises it. Don't set CMD — let the base image's
# default init run.
COPY run.sh /etc/services.d/outback_mate3/run
RUN chmod a+x /etc/services.d/outback_mate3/run
