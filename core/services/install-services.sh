#!/usr/bin/env bash

# Immediately exist on errors
set -e

BUILD_PACKAGES=(
    g++
)

apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

# Wifi service:
## Bind path for wpa
mkdir -p /var/run/wpa_supplicant/
cd /home/pi/services/wifi/ && python3 setup.py install

# Ethernet service:
cd /home/pi/services/cable_guy/ && python3 setup.py install

# Ardupilot manager service:
cd /home/pi/services/ardupilot_manager/ && python3 setup.py install

# Helper service
cd /home/pi/services/helper/ && python3 setup.py install

# Version Chooser service:
cd /home/pi/services/versionchooser/ && python3 setup.py install

# Ping service:
cd /home/pi/services/ping/ && python3 setup.py install

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
