#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

BINARY_NAME="mavp2p"
VERSION="v1.1.1"
GITHUB_REMOTE="https://github.com/bluenviron/mavp2p"

if [ "$RUNNING_IN_CI" ]; then
  LOCAL_BINARY_PATH="/usr/bin/${BINARY_NAME}"
else
  # For some reason python is returning an error code while the output is correct
  LOCAL_BINARY_PATH="$(python -m site --user-base)/bin/${BINARY_NAME}" || true
fi

if [ -f "$LOCAL_BINARY_PATH" ]; then
  echo "File $LOCAL_BINARY_PATH already exists. Skipping download."
  exit 0
fi

mkdir -p "$(dirname "$LOCAL_BINARY_PATH")"

# By default we install armv6
REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavp2p_v1.1.1_linux_armv7.tar.gz"
if [[ "$(uname -m)" == "x86_64"* ]]; then
  REMOTE_BINARY_URL="${GITHUB_REMOTE}/releases/download/${VERSION}/mavp2p_v1.1.1_linux_amd64.tar.gz"
fi

COMPRESS_FILE="$BINARY_NAME.tar.gz"
wget "$REMOTE_BINARY_URL" -O "$COMPRESS_FILE"
tar -xf "$COMPRESS_FILE"
# Binary
cp "$BINARY_NAME" "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"

# Remove temporary files
rm -rf "$COMPRESS_FILE" "${BINARY_NAME}"