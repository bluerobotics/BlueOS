#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/mavlink-camera-manager"

VERSION=t3.3.3

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/bluerobotics/mavlink-camera-manager/releases/download/${VERSION}/mavlink-camera-manager-armv7"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/bluerobotics/mavlink-camera-manager/releases/download/${VERSION}/mavlink-camera-manager-linux-desktop"
fi

# Download and install the camera manager under user binary folder with the correct permissions
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
