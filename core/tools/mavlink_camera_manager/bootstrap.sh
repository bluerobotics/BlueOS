#!/usr/bin/env bash

LOCAL_BINARY_PATH="/usr/bin/mavlink-camera-manager"

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/patrickelectric/mavlink-camera-manager/releases/download/t3.0.2/mavlink-camera-manager-armv7"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/patrickelectric/mavlink-camera-manager/releases/download/t3.0.2/mavlink-camera-manager-linux-desktop"
fi

# Download and install the camera manager under user binary folder with the correct permissions
DEBIAN_FRONTEND=noninteractive apt --yes install wget
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
# Remove necessary stuff to install binary, creating a small docker layer
DEBIAN_FRONTEND=noninteractive apt --yes purge wget
DEBIAN_FRONTEND=noninteractive apt --yes autoremove
