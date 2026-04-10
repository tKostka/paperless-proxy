#!/usr/bin/with-contenv bashio

PAPERLESS_URL=$(bashio::config 'paperless_url')
PAPERLESS_URL="${PAPERLESS_URL%/}"

if [ -z "${PAPERLESS_URL}" ] || [ "${PAPERLESS_URL}" = "null" ]; then
    bashio::log.fatal "paperless_url is not configured! Set it in the add-on configuration."
    exit 1
fi

# Get the Ingress entry path (e.g. /api/hassio_ingress/abc123...)
INGRESS_ENTRY=$(bashio::addon.ingress_entry)
INGRESS_ENTRY="${INGRESS_ENTRY%/}"

bashio::log.info "══════════════════════════════════════════════"
bashio::log.info " Paperless-NGX Proxy v1.3.0"
bashio::log.info " Target:       ${PAPERLESS_URL}"
bashio::log.info " Ingress port: 8099"
bashio::log.info " Ingress path: ${INGRESS_ENTRY}"
bashio::log.info "══════════════════════════════════════════════"

export PAPERLESS_URL
export INGRESS_PORT=8099
export INGRESS_ENTRY

envsubst '${PAPERLESS_URL} ${INGRESS_PORT} ${INGRESS_ENTRY}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

nginx -t 2>&1 || { bashio::log.fatal "nginx config test failed"; exit 1; }

bashio::log.info "Starting nginx..."
exec nginx -g 'daemon off;'
