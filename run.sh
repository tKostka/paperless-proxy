#!/usr/bin/with-contenv bashio

VERSION="2.1.0"

PAPERLESS_URL=$(bashio::config 'paperless_url')
PAPERLESS_URL="${PAPERLESS_URL%/}"

if [ -z "${PAPERLESS_URL}" ] || [ "${PAPERLESS_URL}" = "null" ]; then
    bashio::log.fatal "paperless_url is not configured! Set it in the add-on configuration."
    exit 1
fi

INGRESS_ENTRY=$(bashio::addon.ingress_entry)
INGRESS_ENTRY="${INGRESS_ENTRY%/}"

PAPERLESS_USER=$(bashio::config 'paperless_user' 2>/dev/null || echo "")
[ "${PAPERLESS_USER}" = "null" ] && PAPERLESS_USER=""

bashio::log.info "══════════════════════════════════════════════"
bashio::log.info " Paperless-NGX Proxy v${VERSION}"
bashio::log.info " Target:       ${PAPERLESS_URL}"
bashio::log.info " Ingress port: 8099"
bashio::log.info " Ingress path: ${INGRESS_ENTRY}"
if [ -n "${PAPERLESS_USER}" ]; then
    bashio::log.info " Auto-login:   ${PAPERLESS_USER} (Remote-User)"
else
    bashio::log.info " Auto-login:   disabled"
fi
bashio::log.info "══════════════════════════════════════════════"

export PAPERLESS_URL
export INGRESS_PORT=8099
export INGRESS_ENTRY
export PAPERLESS_USER

exec python3 /app/proxy.py
