#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/mavlink-routerd"
VERSION="blueos-0.1"
GITHUB_REMOTE="https://github.com/patrickelectric/mavlink-router"

# By default we install armv6
REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-glibc-armhf"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-musl-x86-64"
fi

wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"