ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and build dependencies
# Installeer Python en bouwafhankelijkheden
RUN apk add --no-cache \
    python3 \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    mariadb-dev \
    mariadb-connector-c-dev

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt \
    || pip install --no-cache-dir -r requirements.txt

COPY collectors/   /app/collectors/
COPY config/       /app/config/
COPY database/     /app/database/
COPY gui/          /app/gui/
COPY inverter/     /app/inverter/
COPY optimizer/    /app/optimizer/
COPY providers/    /app/providers/
COPY reporter/     /app/reporter/
COPY scheduler/    /app/scheduler/
COPY translations/ /app/translations/
COPY main.py       /app/main.py
COPY uninstall.py  /app/uninstall.py

RUN echo '#!/bin/sh' > /app/run \
    && echo 'set -e' >> /app/run \
    && echo 'cd /app' >> /app/run \
    && echo 'python3 -m flask --app gui/app.py run --host 0.0.0.0 --port 8099 --no-debugger &' >> /app/run \
    && echo 'exec python3 main.py' >> /app/run \
    && chmod 755 /app/run

CMD ["/app/run"]

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization" \
    io.hass.type="addon" \
    io.hass.version="0.1.0-alpha" \
    maintainer="Ludo Thijssen"
