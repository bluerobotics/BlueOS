#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Nginx works as a reverse proxy to merge all services into one server
echo "Installing nginx."
apt update
apt install --no-install-recommends --no-install-suggests -y nginx

echo "Configure HTTPS"
SSL_PATH=/etc/nginx/ssl
mkdir -p "$SSL_PATH"
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout $SSL_PATH/nginx.key \
    -out $SSL_PATH/nginx.crt \
    -subj "/C=US/ST=California/L=Torrance/O=BlueRobotics/CN=blueos.local"
