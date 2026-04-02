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

COPY . /app/

RUN chmod +x /app/run.sh

LABEL \
    io.hass.name="HA Energy Optimizer" \
    io.hass.description="Smart home battery optimization with dynamic energy pricing" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    maintainer="Ludo <ludo@thijssen-fabw.nl>"

CMD ["/app/run.sh"]
