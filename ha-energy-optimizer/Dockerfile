ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    mariadb-dev \
    mariadb-connector-c-dev \
    python3-dev

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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

# Create run script with plain /bin/sh — no bashio, no s6 conflicts
# Maak run-script aan met /bin/sh — geen bashio, geen s6-conflicten
RUN printf '#!/bin/sh\n\
set -e\n\
echo "Starting HA Energy Optimizer..."\n\
\n\
# Write HA config to options.json\n\
if [ -f /etc/s6-overlay/init-catchall ]; then\n\
    echo "s6 environment detected"\n\
fi\n\
\n\
# Copy config from HA supervisor\n\
cat /data/options.json > /tmp/options_check.json 2>/dev/null || echo "options.json not yet available"\n\
\n\
cd /app\n\
\n\
# Start GUI in background\n\
python3 -m flask --app gui/app.py run --host 0.0.0.0 --port 8099 --no-debugger &\n\
echo "GUI started on port 8099"\n\
\n\
# Start optimizer as main process\n\
echo "Starting optimizer engine..."\n\
exec python3 main.py\n\
' > /app/run && chmod 755 /app/run

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization" \
    io.hass.type="addon" \
    io.hass.version="0.1.0-alpha" \
    maintainer="Ludo Thijssen"
