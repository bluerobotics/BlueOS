#!/usr/bin/env bash

DESTINATION_PATH="/home/pi/tools/logviewer"

VERSION=v0.9.1

REMOTE_URL="https://github.com/Ardupilot/UAVLogViewer/releases/download/${VERSION}/logviewer.tar.gz"

# Download uncompress, and move the contents of dist to the target destination
wget $REMOTE_URL
tar -zxf logviewer.tar.gz
mkdir -p $DESTINATION_PATH
mv dist/* $DESTINATION_PATH
rm -r dist
rm -r logviewer.tar.gz