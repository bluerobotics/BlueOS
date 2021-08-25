#!/usr/bin/env bash

## Download and install necessary tools to user binary folder with the correct permissions

### Ardupilot's uploader is used to upload firmwares to serial boards
COMMIT_HASH=4ea8c32c61781fa36dff9748fe3a18cdb5743abb
LOCAL_PATH_UPLOADER="/usr/bin/ardupilot_fw_uploader.py"
REMOTE_URL_UPLOADER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/uploader.py"
wget "$REMOTE_URL_UPLOADER" -O "$LOCAL_PATH_UPLOADER"
chmod +x "$LOCAL_PATH_UPLOADER"

## Download and install necessary modules to user-site folder

USER_SITE_PACKAGES="$(python -m site --user-site)"
mkdir -p $USER_SITE_PACKAGES

### Ardupilot's decoder is used to parse and validate firmware ELF files
COMMIT_HASH=bdb56b20b5cf1f8bf3716c88edb51461f18709a9
LOCAL_PATH_DECODER="${USER_SITE_PACKAGES}/ardupilot_fw_decoder.py"
REMOTE_URL_DECODER="https://raw.githubusercontent.com/patrickelectric/ardupilot/${COMMIT_HASH}/Tools/scripts/firmware_version_decoder.py"
wget "$REMOTE_URL_DECODER" -O "$LOCAL_PATH_DECODER"
