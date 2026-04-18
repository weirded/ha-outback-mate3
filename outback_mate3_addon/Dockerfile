ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
