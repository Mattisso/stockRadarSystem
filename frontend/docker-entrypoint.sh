#!/bin/sh
set -eu

envsubst < /etc/stock-radar/runtime-config.template.js > /usr/share/nginx/html/runtime-config.js

exec nginx -g 'daemon off;'
