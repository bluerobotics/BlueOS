#!/usr/bin/env bash

# Immediately exit on errors
set -e

BUILD_PACKAGES=(
    g++
)

echo "Target architecture: $TARGETARCH"
echo "Target variant: $TARGETVARIANT"

# psutil requires BUILD_PACKAGES to build to all platforms
apt update
apt install -y --no-install-recommends ${BUILD_PACKAGES[*]}

# Piwheels is a Python package repository providing Arm platform wheels (pre-compiled binary Python packages)
# specifically for the Raspberry Pi, making pip installations much faster.
# Packages are natively compiled on Raspberry Pi 3 and 4 hardware
# Add it regardless of the platform, as it is a fallback index, and will only be used if the package is not found on the main index.
echo "Configuring pip to use piwheels"
echo "[global]" >> /etc/pip.conf
echo "extra-index-url=https://www.piwheels.org/simple" >> /etc/pip.conf

CURRENT_PATH=$(dirname "$0")

# Install libraries

# install pykson = {git = "https://github.com/patrickelectric/pykson.git", rev = "fcab71c1eadd6c6b730ca21a5eecb3bf9c374507"}
pip3 install https://codeload.github.com/patrickelectric/pykson/zip/fcab71c1eadd6c6b730ca21a5eecb3bf9c374507
pip3 install -e $CURRENT_PATH/bridges
pip3 install -e $CURRENT_PATH/commonwealth

apt -y remove ${BUILD_PACKAGES[*]}
apt -y autoremove
apt -y clean
