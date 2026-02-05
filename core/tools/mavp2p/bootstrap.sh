#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

VERSION="v1.1.1"
REPOSITORY_ORG="bluenviron"
REPOSITORY_NAME="mavp2p"
PROJECT_NAME="mavp2p"
REPOSITORY_URL="https://github.com/$REPOSITORY_ORG/$REPOSITORY_NAME"

echo "Installing project $PROJECT_NAME version $VERSION"

# Step 1: Prepare the download URL

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64 | amd64)
    BUILD_NAME="linux_amd64"
    ;;
  armv7l | armhf)
    BUILD_NAME="linux_armv7"
    ;;
  aarch64 | arm64)
    BUILD_NAME="linux_arm64v8"
    ;;
  *)
    echo "Architecture: $ARCH is unsupported, please create a new issue on https://github.com/bluerobotics/BlueOS/issues"
    exit 1
    ;;
esac
ARTIFACT_NAME="${PROJECT_NAME}_${VERSION}_${BUILD_NAME}.tar.gz"
echo "For architecture $ARCH, using build $BUILD_NAME"

REMOTE_URL="$REPOSITORY_URL/releases/download/$VERSION/$ARTIFACT_NAME"
echo "Remote URL is $REMOTE_URL"

# Step 2: Prepare the installation path

if [ -n "$VIRTUAL_ENV" ]; then
    BIN_DIR="$VIRTUAL_ENV/bin"
else
    BIN_DIR="/usr/bin"
fi
mkdir -p "$BIN_DIR"

BINARY_PATH="$BIN_DIR/$PROJECT_NAME"
echo "Installing to $BINARY_PATH"

# Step 3: Download and install

TMP_DIR=".tmp/$PROJECT_NAME"
mkdir -p "$TMP_DIR"
wget -q "$REMOTE_URL" -O - | tar -zxf - -C "$TMP_DIR"
mv "$TMP_DIR/$PROJECT_NAME" "$BINARY_PATH"
rm -rf "$TMP_DIR"
chmod +x "$BINARY_PATH"
strip "$BINARY_PATH"

echo "Installed binary type: $(file "$(which "$BINARY_PATH")")"

echo "Finished installing $PROJECT_NAME"
