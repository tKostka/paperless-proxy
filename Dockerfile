ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    bash \
    nginx \
    gettext \
    && rm -rf /var/cache/apk/*

COPY nginx.conf.template /etc/nginx/nginx.conf.template

COPY run.sh /etc/services.d/paperless_proxy/run
RUN chmod +x /etc/services.d/paperless_proxy/run
