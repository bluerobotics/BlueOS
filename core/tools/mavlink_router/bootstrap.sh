#!/usr/bin/env bash

# Immediately exit on errors
set -e

VERSION="v4"
REPOSITORY_ORG="mavlink-router"
REPOSITORY_NAME="$REPOSITORY_ORG"
PROJECT_NAME="mavlink-routerd"
REPOSITORY_URL="https://github.com/$REPOSITORY_ORG/$REPOSITORY_NAME"

echo "Installing project $PROJECT_NAME version $VERSION"

# Step 1: Prepare the download URL

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64 | amd64)
    BUILD_NAME="glibc-x86_64"
    ;;
  armv7l | armhf)
    BUILD_NAME="glibc-armhf"
    ;;
  aarch64 | arm64)
    BUILD_NAME="glibc-aarch64"
    ;;
  *)
    echo "Architecture: $ARCH is unsupported, please create a new issue on https://github.com/bluerobotics/BlueOS/issues"
    exit 1
    ;;
esac
ARTIFACT_NAME="$PROJECT_NAME-$BUILD_NAME"
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

wget -q "$REMOTE_URL" -O "$BINARY_PATH"
chmod +x "$BINARY_PATH"
strip "$BINARY_PATH"

echo "Installed binary type: $(file "$(which "$BINARY_PATH")")"

echo "Finished installing $PROJECT_NAME"
