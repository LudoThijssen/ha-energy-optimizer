#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting HA Energy Optimizer..."

bashio::config > /data/options.json

if ! bashio::config.has_value "database.host"; then
    bashio::log.fatal "Database host is not configured"
    exit 1
fi

if ! bashio::config.has_value "homeassistant.token"; then
    bashio::log.fatal "Home Assistant token is not configured"
    exit 1
fi

bashio::log.info "Starting configuration GUI on port 8099..."
cd /app
python3 -m flask --app gui/app.py run \
    --host 0.0.0.0 \
    --port 8099 \
    --no-debugger \
    &

bashio::log.info "Starting optimizer engine..."
cd /app
exec python3 main.py
