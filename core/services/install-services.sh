#!/usr/bin/env bash

# Immediately exist on errors
set -e

BUILD_PACKAGES=(
    g++
)

apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

# Pre-Build dependencies:
# For convenience, we build ourselves the .wheel packages for dependencies
# which have no armv7 wheel in pypi. This saves a lot of build time in docker
if [[ "$(uname -m)" == "armv7l"* ]]; then
    pip install https://s3.amazonaws.com/downloads.bluerobotics.com/companion-docker/wheels/aiohttp-3.7.4-cp39-cp39-linux_armv7l.whl
fi

# Wifi service:
## Bind path for wpa
mkdir -p /var/run/wpa_supplicant/
cd /home/pi/services/wifi/ && python3 setup.py install

# Ethernet service:
cd /home/pi/services/cable_guy/ && python3 setup.py install

# Ardupilot manager service:
cd /home/pi/services/ardupilot_manager/ && python3 setup.py install

# Bridget service:
cd /home/pi/services/bridget/ && python3 setup.py install

# Helper service
cd /home/pi/services/helper/ && python3 setup.py install

# Version Chooser service:
cd /home/pi/services/versionchooser/ && python3 setup.py install

# Ping service:
cd /home/pi/services/ping/ && python3 setup.py install

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
