#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "checking sudo"
SUDO="$(command -v sudo || echo '')"
echo "making sudo readonly"
readonly SUDO

LOCAL_BINARY_PATH="/usr/bin/mavlink-routerd" || true
echo "Installing mavlink-routerd to: ${LOCAL_BINARY_PATH}"
VERSION="companion-core-development-0.1"
GITHUB_REMOTE="https://github.com/patrickelectric/mavlink-router"

# By default we install armv6
REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-libc-armv6"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavlink-routerd-libc-x86-64"
fi

$SUDO wget "$REMOTE_BINARY_URL" -O "$LOCAL_BINARY_PATH"
$SUDO chmod +x "$LOCAL_BINARY_PATH"
