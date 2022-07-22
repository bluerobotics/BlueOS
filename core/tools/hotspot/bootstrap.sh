#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Hostapd turns a network wireless interface into a wifi hotspot
echo "Installing hostapd."
apt install -y --no-install-recommends hostapd

# Iw and net-tools are used by the hotspot manager to configure the network interfaces
echo "Installing iw and net-tools."
apt install -y --no-install-recommends iw
apt install -y --no-install-recommends net-tools
