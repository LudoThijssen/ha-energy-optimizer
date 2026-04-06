ARG BUILD_FROM
FROM ${BUILD_FROM}

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
RUN pip install --no-cache-dir -r requirements.txt \
    || pip install --no-cache-dir --break-system-packages -r requirements.txt

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

# Copy s6 service definition / Kopieer s6-servicedefinitie
COPY rootfs/ /
RUN chmod a+x /etc/services.d/energy-optimizer/run

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization" \
    io.hass.type="addon" \
    io.hass.version="0.1.0-alpha" \
    maintainer="Ludo Thijssen"
