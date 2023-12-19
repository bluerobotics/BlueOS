#!/usr/bin/env bash

# Immediately exit on errors
set -e

BUILD_PACKAGES=(
    g++
)

apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

# Piwheels is a Python package repository providing Arm platform wheels (pre-compiled binary Python packages)
# specifically for the Raspberry Pi, making pip installations much faster.
# Packages are natively compiled on Raspberry Pi 3 and 4 hardware
if [[ "$(uname -m)" == "arm"* ]]; then
    echo "Configuring pip to use piwheels"
    echo "[global]" >> /etc/pip.conf
    echo "extra-index-url=https://www.piwheels.org/simple" >> /etc/pip.conf
fi

CURRENT_PATH=$(dirname "$0")

# Install libraries
python3 $CURRENT_PATH/bridges/setup.py install
python3 $CURRENT_PATH/commonwealth/setup.py install

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
