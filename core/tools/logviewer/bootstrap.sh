#!/usr/bin/env bash

# Immediately exit on errors
set -e

DESTINATION_PATH="/home/pi/tools/logviewer"

VERSION=v1.0.1

REMOTE_URL="https://github.com/Ardupilot/UAVLogViewer/releases/download/${VERSION}/logviewer.tar.gz"

# Download uncompress, and move the contents of dist to the target destination
wget $REMOTE_URL
tar -zxf logviewer.tar.gz
mkdir -p $DESTINATION_PATH
mv dist/* $DESTINATION_PATH
find $DESTINATION_PATH -name "*.gz" -type f -delete
rm -r dist
rm -r logviewer.tar.gz