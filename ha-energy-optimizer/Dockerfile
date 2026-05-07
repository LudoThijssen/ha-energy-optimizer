# Version 0.2.10
# /ha-energy-optimizer/Dockerfile
# 2026-04-25 21:55

ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and dependencies
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

# Copy s6 service definition
COPY rootfs/ /

# Recreate run script with Unix line endings to avoid CRLF issues
# Hermaak run-script met Unix regeleindes om CRLF problemen te voorkomen
RUN printf '#!/usr/bin/with-contenv bashio\nset -e\nbashio::log.info "Starting HA Energy Optimizer v0.2.10..."\nOPTIONS_FILE="/data/options.json"\nif [ -f "${OPTIONS_FILE}" ] && [ -s "${OPTIONS_FILE}" ]; then\n    bashio::log.info "Using existing options.json"\nelse\n    bashio::log.info "Fetching configuration from supervisor..."\n    curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/addons/self/options/config > "${OPTIONS_FILE}" || echo "{}" > "${OPTIONS_FILE}"\nfi\nbashio::log.info "Configuration ready"\nfuser -k 8099/tcp 2>/dev/null || true\nbashio::log.info "Starting configuration GUI on port 8099..."\ncd /app\npython3 -m flask --app gui/app.py run --host 0.0.0.0 --port 8099 --no-debugger &\nbashio::log.info "Starting optimizer engine..."\nexec python3 main.py\n' > /etc/services.d/energy-optimizer/run && chmod 755 /etc/services.d/energy-optimizer/run

ARG CACHEBUST=1
RUN echo "Cache bust: $CACHEBUST"
