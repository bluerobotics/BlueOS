#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/mavlink-camera-manager"
ARTIFACT_PREFIX="mavlink-camera-manager"
VERSION="t3.13.1"

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/mavlink/mavlink-camera-manager/releases/download/${VERSION}/${ARTIFACT_PREFIX}-armv7"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/mavlink/mavlink-camera-manager/releases/download/${VERSION}/${ARTIFACT_PREFIX}-linux-desktop"
elif [[ "$(uname -m)" == "aarch64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/mavlink/mavlink-camera-manager/releases/download/${VERSION}/${ARTIFACT_PREFIX}-aarch64"
fi

# Download and install the camera manager under user binary folder with the correct permissions
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
