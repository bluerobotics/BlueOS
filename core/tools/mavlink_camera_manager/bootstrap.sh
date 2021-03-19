#!/usr/bin/env bash

LOCAL_BINARY_PATH="/usr/bin/mavlink-camera-manager"
REMOTE_BINARY_URL="https://s3.amazonaws.com/downloads.bluerobotics.com/companion-docker/tools/mavlink-camera-manager"

# Download and install the camera manager under user binary folder with the correct permissions
DEBIAN_FRONTEND=noninteractive apt --yes install wget
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
# Remove necessary stuff to install binary, creating a small docker layer
DEBIAN_FRONTEND=noninteractive apt --yes purge wget
DEBIAN_FRONTEND=noninteractive apt --yes autoremove
