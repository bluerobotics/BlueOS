#!/usr/bin/env bash

# Immediately exit on errors
set -e

LOCAL_BINARY_PATH="/usr/bin/mavlink2rest"

VERSION=t0.11.19

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/mavlink/mavlink2rest/releases/download/${VERSION}/mavlink2rest-armv7-unknown-linux-musleabihf"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/mavlink/mavlink2rest/releases/download/${VERSION}/mavlink2rest-x86_64-unknown-linux-musl"
fi

# Download and install mavlink2rest under user binary folder with the correct permissions
wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
