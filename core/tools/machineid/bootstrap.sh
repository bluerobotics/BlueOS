#!/usr/bin/env bash

# Immediately exit on errors
set -e

LOCAL_BINARY_PATH="/usr/bin/machineid-cli"
VERSION=0.2.1

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/patrickelectric/machineid-cli/releases/download/${VERSION}/machineid-cli-armv7-unknown-linux-musleabihf"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/patrickelectric/machineid-cli/releases/download/${VERSION}/machineid-cli-x86_64-unknown-linux-musl"
fi

wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
