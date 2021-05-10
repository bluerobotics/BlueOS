#!/usr/bin/env bash

LOCAL_BINARY_PATH="/usr/bin/bridges"
VERSION=0.5.0

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/patrickelectric/bridges/releases/download/${VERSION}/bridges-armv7-unknown-linux-musleabihf"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/patrickelectric/bridges/releases/download/${VERSION}/bridges-x86_64-unknown-linux-musl"
fi

DEBIAN_FRONTEND=noninteractive apt --yes install wget
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
# Remove necessary stuff to install binary, creating a small docker layer
## Some libraries are still necessary
DEBIAN_FRONTEND=noninteractive apt --yes purge wget
DEBIAN_FRONTEND=noninteractive apt --yes autoremove