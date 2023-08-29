#!/usr/bin/env bash

# Immediately exit on errors
set -e

BUILD_PACKAGES=(
    g++
)

apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

# Install all consolidated dependencies
pip install -r /home/pi/services/requirements.txt

# Wifi service:
## Bind path for wpa
mkdir -p /var/run/wpa_supplicant/

# Install services
SERVICES=(
    ardupilot_manager
    bag_of_holding
    beacon
    bridget
    cable_guy
    commander
    helper
    kraken
    nmea_injector
    ping
    versionchooser
    wifi
)

for SERVICE in "${SERVICES[@]}"; do
    echo "Installing service: $SERVICE"
    cd "/home/pi/services/$SERVICE/" && python3 setup.py install
done

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
