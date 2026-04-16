# Version 0.2.6.1
# /ha-energy-optimizer/Dockerfile
# 12-04-2026 21:50

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

ARG CACHEBUST=1
RUN echo "Cache bust: $CACHEBUST"
