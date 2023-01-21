#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/mavlink-camera-manager"
ARTIFACT_PREFIX="mavlink-camera-manager"
VERSION=t3.10.0

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/bluerobotics/mavlink-camera-manager/releases/download/${VERSION}/${ARTIFACT_PREFIX}-armv7.zip"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/bluerobotics/mavlink-camera-manager/releases/download/${VERSION}/${ARTIFACT_PREFIX}-linux-desktop.zip"
fi

# Download and install the camera manager under user binary folder with the correct permissions
ARTIFACT_PREFIX="mavlink-camera-manager"
wget "$REMOTE_BINARY_URL" -O "${ARTIFACT_PREFIX}.zip"
unzip "${ARTIFACT_PREFIX}.zip" -d "${ARTIFACT_PREFIX}"
# Binary
cp "${ARTIFACT_PREFIX}/${ARTIFACT_PREFIX}"* "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"

# Remove temporary files
rm -rf "${ARTIFACT_PREFIX}.zip" "${ARTIFACT_PREFIX}"
