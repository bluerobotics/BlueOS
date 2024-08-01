#!/usr/bin/env bash

# Immediately exit on errors
set -e

BUILD_PACKAGES=(
    g++
)

# Install build packages if not on armv7, which we have all pre-built wheels for
if ! { [ "$TARGETARCH" == "arm" ] && [ "$TARGETVARIANT" == "v7" ]; }; then
    apt update
    apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}
fi

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
# Install the BlueOS Extensions Repository
python -m pip install  https://github.com/JoaoMario109/BlueOS-Extensions-Repository/tarball/0.0.1\#egg\=blueos-extensions-repository

for SERVICE in "${SERVICES[@]}"; do
    echo "Installing service: $SERVICE"
    cd "/home/pi/services/$SERVICE/" && pip3 install .
done

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
