#!/bin/bash

# Immediately exit on errors
set -e

PROJECT_NAME="zenoh"
VERSION="1.7.2"
BINARIES=(
  "zenoh"
  "zenoh-plugin-webserver"
  "zenoh-backend-filesystem"
  "zenoh-plugin-remote-api/zenoh-ts"
)

echo "Installing project $PROJECT_NAME and friends with version $VERSION"

# Step 1: Prepare the download URL

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64 | amd64)
    TOOLCHAIN="x86_64-unknown-linux-gnu"
    ;;
  armv7l | armhf)
    TOOLCHAIN="armv7-unknown-linux-gnueabihf"
    ;;
  aarch64 | arm64)
    TOOLCHAIN="aarch64-unknown-linux-gnu"
    ;;
  *)
    echo "Architecture: $ARCH is unsupported, please create a new issue on https://github.com/bluerobotics/BlueOS/issues"
    exit 1
    ;;
esac
echo "For architecture $ARCH, using toolchain $TOOLCHAIN"

# Step 2: Prepare the installation and tools paths

if [ -n "$VIRTUAL_ENV" ]; then
    BIN_DIR="$VIRTUAL_ENV/bin"
else
    BIN_DIR="/usr/bin"
fi

BINARY_PATH="$BIN_DIR/$PROJECT_NAME"

mkdir -p "$BINARY_PATH"

# Step 3: Download and install the binaries
echo "Downloading binaries..."

DOWNLOAD_FOLDER="/tmp/zenoh_and_friends"
mkdir -p "$DOWNLOAD_FOLDER"
for BINARY in "${BINARIES[@]}"; do
  if [[ "$BINARY" == *"/"* ]]; then
    BINARY_URL_PATH="${BINARY%/*}"
    BINARY_URL_NAME="${BINARY##*/}"
  else
    BINARY_URL_PATH="$BINARY"
    BINARY_URL_NAME="$BINARY"
  fi

  URL="https://download.eclipse.org/zenoh/${BINARY_URL_PATH}/${VERSION}/${BINARY_URL_NAME}-${VERSION}-${TOOLCHAIN}-standalone.zip"
  echo " - Download: ${URL}"
  wget -q "$URL" -O "${DOWNLOAD_FOLDER}/${BINARY_URL_PATH}.zip"
done
echo "Downloaded all binaries, now installing to $BINARY_PATH"

cd "$DOWNLOAD_FOLDER"
unzip "*.zip"
rm -- ./*.zip
INSTALLED_FILES=(*)
mv -- ./* "$BINARY_PATH"
cd - && rm -rf "$DOWNLOAD_FOLDER"

for BINARY in "${INSTALLED_FILES[@]}"; do
  echo "Installed binary type: $(file "$(which "$BINARY_PATH/$BINARY")")"
done
echo "Finished installing $PROJECT_NAME"
