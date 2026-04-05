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

# Create run script directly in Docker — avoids Windows CRLF line ending issues
# Maak run-script direct aan in Docker — voorkomt Windows CRLF regeleindeprobleem
RUN printf '#!/usr/bin/bashio\n\
set -e\n\
bashio::log.info "Starting HA Energy Optimizer..."\n\
bashio::config > /data/options.json\n\
bashio::log.info "Configuration written"\n\
cd /app\n\
python3 -m flask --app gui/app.py run --host 0.0.0.0 --port 8099 --no-debugger &\n\
bashio::log.info "GUI started on port 8099"\n\
bashio::log.info "Starting optimizer engine..."\n\
exec python3 main.py\n\
' > /app/run && chmod a+x /app/run

# Remove any CRLF from run script just in case
# Verwijder eventuele CRLF uit het run-script voor de zekerheid
RUN sed -i 's/\r//' /app/run

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization" \
    io.hass.type="addon" \
    io.hass.version="0.1.0-alpha" \
    maintainer="Ludo Thijssen"
