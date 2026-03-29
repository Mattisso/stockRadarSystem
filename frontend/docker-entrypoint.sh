#!/bin/sh
set -eu

export FRONTEND_API_BASE_URL="${FRONTEND_API_BASE_URL:-/api}"
export FRONTEND_WS_BASE_URL="${FRONTEND_WS_BASE_URL:-}"

envsubst < /etc/stock-radar/runtime-config.template.js > /usr/share/nginx/html/runtime-config.js

exec nginx -g 'daemon off;'
