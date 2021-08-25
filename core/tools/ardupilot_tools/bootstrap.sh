#!/usr/bin/env bash

# Download and install necessary tools to user binary folder with the correct permissions

# Ardupilot's uploader is used to upload firmwares to serial boards
COMMIT_HASH=4ea8c32c61781fa36dff9748fe3a18cdb5743abb
LOCAL_PATH_UPLOADER="/usr/bin/ardupilot_fw_uploader.py"
REMOTE_URL_UPLOADER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/uploader.py"
wget "$REMOTE_URL_UPLOADER" -O "$LOCAL_PATH_UPLOADER"
chmod +x "$LOCAL_PATH_UPLOADER"
