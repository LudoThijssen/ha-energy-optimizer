ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

# Install system dependencies / Installeer systeemafhankelijkheden
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    mariadb-dev \
    mariadb-connector-c-dev \
    python3-dev

# Install Python dependencies first (better layer caching)
# Installeer Python-afhankelijkheden eerst (betere laagcaching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all addon Python files / Kopieer alle add-on Python-bestanden
COPY collectors/      /app/collectors/
COPY config/          /app/config/
COPY database/        /app/database/
COPY gui/             /app/gui/
COPY inverter/        /app/inverter/
COPY optimizer/       /app/optimizer/
COPY providers/       /app/providers/
COPY reporter/        /app/reporter/
COPY scheduler/       /app/scheduler/
COPY translations/    /app/translations/
COPY main.py          /app/main.py
COPY uninstall.py     /app/uninstall.py

# Copy s6-overlay service definitions
# Kopieer s6-overlay servicedefinities
COPY rootfs/ /

# Make service scripts executable / Maak servicescripts uitvoerbaar
RUN chmod a+x \
    /etc/s6-overlay/s6-rc.d/energy-optimizer/run \
    /etc/s6-overlay/s6-rc.d/gui-optimizer/run

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization with dynamic energy pricing" \
    io.hass.type="addon" \
    io.hass.version="0.1.0-alpha" \
    maintainer="Ludo Thijssen"
