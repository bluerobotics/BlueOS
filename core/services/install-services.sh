#!/usr/bin/env bash

# Immediately exit on errors
set -e

BUILD_PACKAGES=(
    g++
)

apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

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

# We need to install loguru, appdirs and pydantic since they may be used inside setup.py
python -m pip install appdirs==1.4.4 loguru==0.5.3 pydantic==1.10.12

for SERVICE in "${SERVICES[@]}"; do
    echo "Installing service: $SERVICE"
    cd "/home/pi/services/$SERVICE/" && python3 setup.py install
done

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
