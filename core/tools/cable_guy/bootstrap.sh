#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Hostapd turns a network wireless interface into a wifi hotspot
echo "Installing ifmetric."
apt update
apt install -y --no-install-recommends ifmetric
