#!/usr/bin/env bash

# Immediately exit on errors
set -e

LOCAL_BINARY_PATH="/usr/bin/filebrowser"
VERSION=v2.24.2

# By default we install armv7
REMOTE_BINARY_URL="https://github.com/filebrowser/filebrowser/releases/download/${VERSION}/linux-armv7-filebrowser.tar.gz"
if [[ "$(uname -m)" == "x86_64"* ]]; then
    REMOTE_BINARY_URL="https://github.com/filebrowser/filebrowser/releases/download/${VERSION}/linux-amd64-filebrowser.tar.gz"
fi

wget "$REMOTE_BINARY_URL" -O - | tar xz -C /usr/bin/
chmod +x "$LOCAL_BINARY_PATH"

# Create configuration file
DATABASE_PATH="/etc/filebrowser/filebrowser.db"
mkdir -p $(dirname "$DATABASE_PATH")
filebrowser config init --address=0.0.0.0 --port=7777 --auth.method=noauth --log=stdout --root=/shortcuts --database="$DATABASE_PATH"
filebrowser users add pi raspberry --database="$DATABASE_PATH"