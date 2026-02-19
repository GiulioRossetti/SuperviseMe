#!/bin/sh
set -eu

CERT_PATH="/etc/nginx/ssl/superviseme.crt"
KEY_PATH="/etc/nginx/ssl/superviseme.key"

if [ ! -f "$CERT_PATH" ]; then
  echo "ERROR: Missing TLS certificate at $CERT_PATH"
  exit 1
fi

if [ ! -f "$KEY_PATH" ]; then
  echo "ERROR: Missing TLS private key at $KEY_PATH"
  exit 1
fi

exec nginx -g "daemon off;"
