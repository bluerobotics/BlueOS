#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Nginx works as a reverse proxy to merge all services into one server
echo "Installing nginx."
apt update
apt install --no-install-recommends --no-install-suggests -y nginx
