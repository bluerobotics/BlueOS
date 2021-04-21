#!/usr/bin/env bash

LOCAL_BINARY_PATH="/usr/bin/linux2rest"
VERSION=v0.1.3

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/patrickelectric/linux2rest/releases/download/${VERSION}/linux2rest-armv7"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/patrickelectric/linux2rest/releases/download/${VERSION}/linux2rest-x86_64"
fi

# Download and install necessary libraries for linux2rest
DEBIAN_FRONTEND=noninteractive apt --yes install wget libudev-dev
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
# Remove necessary stuff to install binary, creating a small docker layer
## Some libraries are still necessary
DEBIAN_FRONTEND=noninteractive apt --yes purge wget
DEBIAN_FRONTEND=noninteractive apt --yes autoremove
