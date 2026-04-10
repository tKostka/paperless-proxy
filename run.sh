#!/usr/bin/env bash
set -e

# Read option from HA addon config
PAPERLESS_URL=$(bashio::config 'paperless_url')

# Strip trailing slash
PAPERLESS_URL="${PAPERLESS_URL%/}"

bashio::log.info "Starting Paperless-NGX Proxy → ${PAPERLESS_URL}"

# Export for envsubst
export PAPERLESS_URL
export INGRESS_PORT=8099

# Render nginx config from template
envsubst '${PAPERLESS_URL} ${INGRESS_PORT}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

# Validate config
nginx -t

# Run in foreground
exec nginx -g 'daemon off;'
