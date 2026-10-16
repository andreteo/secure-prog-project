#!/bin/sh
# Create a disposable certificate for the localhost HTTPS presentation.
set -eu
umask 077

cd "$(dirname "$0")/.."
mkdir -p local-certs
if [ -e local-certs/localhost.key ] || [ -e local-certs/localhost.crt ]; then
    echo 'Local certificate already exists; remove both files to regenerate it.' >&2
    exit 1
fi

openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 30 \
    -keyout local-certs/localhost.key \
    -out local-certs/localhost.crt \
    -subj '/CN=localhost' \
    -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' \
    -addext 'basicConstraints=critical,CA:FALSE'

echo 'Created local-certs/localhost.crt and local-certs/localhost.key'
