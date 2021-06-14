#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Dnsmasq provides DHCP and DNS servers for small networks
echo "Installing dnsmasq."
apt install -y --no-install-recommends dnsmasq
