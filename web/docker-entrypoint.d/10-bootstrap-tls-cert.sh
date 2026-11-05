#!/bin/sh
# A self-signed certificate so nginx always starts.
#
# The 443 listener names two files. Without them nginx refuses to start at all,
# which would mean a failed certificate issuance -- or a first boot before one was
# ever requested -- takes the whole web container down, including the plain-HTTP
# LAN access that has nothing to do with TLS. A placeholder keeps that failure
# proportionate: the site stays up and the browser complains about the certificate
# instead of showing nothing.
#
# acme.sh writes the real pair over these same paths. Nothing here ever overwrites
# a file that already exists.
set -eu

CERT_DIR="${TLS_CERT_DIR:-/etc/nginx/certs}"
CERT="$CERT_DIR/fullchain.pem"
KEY="$CERT_DIR/privkey.pem"

if [ -s "$CERT" ] && [ -s "$KEY" ]; then
    echo "TLS: using the certificate already in $CERT_DIR"
    exit 0
fi

echo "TLS: no certificate in $CERT_DIR, generating a self-signed placeholder"
mkdir -p "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -subj "/CN=${TLS_SELF_SIGNED_CN:-burnrate.local}" \
    -keyout "$KEY" -out "$CERT" >/dev/null 2>&1
chmod 600 "$KEY"
