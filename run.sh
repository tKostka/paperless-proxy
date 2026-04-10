#!/usr/bin/with-contenv bashio

VERSION="1.5.0"

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
bashio::log.info " Paperless-NGX Proxy v${VERSION}"
bashio::log.info " Target:       ${PAPERLESS_URL}"
bashio::log.info " Ingress port: 8099"
bashio::log.info " Ingress path: ${INGRESS_ENTRY}"
bashio::log.info "══════════════════════════════════════════════"

export PAPERLESS_URL
export INGRESS_PORT=8099
export INGRESS_ENTRY

# Prepare log directory
mkdir -p /var/log/nginx
: > /var/log/nginx/access.log

# Render nginx config
envsubst '${PAPERLESS_URL} ${INGRESS_PORT} ${INGRESS_ENTRY}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

# Render debug page with current values
sed -e "s|__VERSION__|${VERSION}|g" \
    -e "s|__PAPERLESS_URL__|${PAPERLESS_URL}|g" \
    -e "s|__INGRESS_ENTRY__|${INGRESS_ENTRY}|g" \
    /usr/share/nginx/debug.html > /tmp/debug.html
cp /tmp/debug.html /usr/share/nginx/debug.html

nginx -t 2>&1 || { bashio::log.fatal "nginx config test failed"; exit 1; }

bashio::log.info "Starting nginx..."
bashio::log.info "Debug page: <ingress_url>/debug"
exec nginx -g 'daemon off;'
