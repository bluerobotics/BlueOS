#!/usr/bin/env bash

# Immediately exit on errors
set -e

VERSION="v1.0.1"
REPOSITORY_ORG="Ardupilot"
REPOSITORY_NAME="UAVLogViewer"
PROJECT_NAME="logviewer"
REPOSITORY_URL="https://github.com/$REPOSITORY_ORG/$REPOSITORY_NAME"

echo "Installing project $PROJECT_NAME version $VERSION"

# Step 1: Prepare the download URL

ARCH="$(uname -m)"
ARTIFACT_NAME="$PROJECT_NAME.tar.gz"
echo "For architecture $ARCH, using build $BUILD_NAME"

REMOTE_URL="$REPOSITORY_URL/releases/download/$VERSION/$ARTIFACT_NAME"
echo "Remote URL is $REMOTE_URL"

# Step 2: Prepare the installation path

INSTALL_FOLDER="/var/www/html/$PROJECT_NAME"
mkdir -p "$INSTALL_FOLDER"

echo "Installing to $INSTALL_FOLDER"

# Step 3: Download and install

wget -q "$REMOTE_URL" -O - | tar -zxf - -C "$INSTALL_FOLDER"
find "$INSTALL_FOLDER/dist" -name "*.gz" -type f -delete
mv "$INSTALL_FOLDER"/dist/* "$INSTALL_FOLDER"
rm -rf "$INSTALL_FOLDER/dist"

echo "Finished installing $PROJECT_NAME"
