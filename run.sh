#!/usr/bin/with-contenv bashio

PAPERLESS_URL=$(bashio::config 'paperless_url')
PAPERLESS_URL="${PAPERLESS_URL%/}"

if [ -z "${PAPERLESS_URL}" ] || [ "${PAPERLESS_URL}" = "null" ]; then
    bashio::log.fatal "paperless_url is not configured! Set it in the add-on configuration."
    exit 1
fi

bashio::log.info "══════════════════════════════════════════════"
bashio::log.info " Paperless-NGX Proxy v1.2.1"
bashio::log.info " Target: ${PAPERLESS_URL}"
bashio::log.info " Ingress port: 8099"
bashio::log.info "══════════════════════════════════════════════"

export PAPERLESS_URL
export INGRESS_PORT=8099

envsubst '${PAPERLESS_URL} ${INGRESS_PORT}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

nginx -t 2>&1 || { bashio::log.fatal "nginx config test failed"; exit 1; }

bashio::log.info "Starting nginx..."
exec nginx -g 'daemon off;'
