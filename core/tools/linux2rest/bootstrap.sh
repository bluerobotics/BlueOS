#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

LOCAL_BINARY_PATH="/usr/bin/linux2rest"
VERSION=v0.5.7
REMOTE_BINARY_URL="https://github.com/patrickelectric/linux2rest/releases/download/${VERSION}"
ARTIFACT_NAME="linux2rest-aarch64-unknown-linux-gnu"

case "$(uname -m)" in
  x86_64)
    ARTIFACT_NAME="linux2rest-x86_64-unknown-linux-gnu"
    ;;
  armv[6-8]l)
    ARTIFACT_NAME="linux2rest-armv7-unknown-linux-gnueabihf"
    ;;
  *)
    # By default we use aarch64
    ;;
esac


wget "$REMOTE_BINARY_URL/$ARTIFACT_NAME" -O "$LOCAL_BINARY_PATH"
chmod +x "$LOCAL_BINARY_PATH"
