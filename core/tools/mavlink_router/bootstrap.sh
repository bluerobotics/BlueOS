#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="$(python -m site --user-base)/bin/mavlink-routerd" || true
if [ "$RUNNING_IN_CI" ]; then
    LOCAL_BINARY_PATH="/usr/bin/mavlink-routerd" || true
fi
mkdir -p "$(dirname "$LOCAL_BINARY_PATH")"

echo "Installing mavlink-routerd to: ${LOCAL_BINARY_PATH}"
VERSION="companion-core-development-0.1"
GITHUB_REMOTE="https://github.com/patrickelectric/mavlink-router"

# By default we install armv6
REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-libc-armv6"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-libc-x86-64"
fi
if [ -f "$LOCAL_BINARY_PATH" ]; then
    echo "File $LOCAL_BINARY_PATH already exists. Skipping download."
    exit 0
fi

wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
