ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    bash \
    python3 \
    && rm -rf /var/cache/apk/*

WORKDIR /app
COPY proxy.py .

COPY run.sh /etc/services.d/paperless_proxy/run
RUN chmod +x /etc/services.d/paperless_proxy/run
