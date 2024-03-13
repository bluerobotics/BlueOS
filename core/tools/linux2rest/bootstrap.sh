#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/linux2rest"
VERSION=v0.5.4

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/patrickelectric/linux2rest/releases/download/${VERSION}/linux2rest-armv7"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/patrickelectric/linux2rest/releases/download/${VERSION}/linux2rest-x86_64"
fi

# Download and install necessary libraries for linux2rest
DEBIAN_FRONTEND=noninteractive apt update && apt install -y libudev-dev
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
