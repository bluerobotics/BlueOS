#!/usr/bin/env bash

# Immediately exit on errors
set -e

## Download and install necessary tools to user binary folder with the correct permissions

### Ardupilot's uploader is used to upload firmwares to serial boards
COMMIT_HASH=4ea8c32c61781fa36dff9748fe3a18cdb5743abb
LOCAL_PATH_UPLOADER="/usr/bin/ardupilot_fw_uploader.py"
REMOTE_URL_UPLOADER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/uploader.py"

# Sudo command is not available on docker and the script is also used in different environments
# The SUDO alias allow the usage of sudo when such command exists and also ignore if it doesn't
SUDO="$(command -v sudo || echo '')"
readonly SUDO
$SUDO wget "$REMOTE_URL_UPLOADER" -O "$LOCAL_PATH_UPLOADER"
$SUDO chmod +x "$LOCAL_PATH_UPLOADER"

## Download and install necessary modules to user-site folder

USER_SITE_PACKAGES="$(python -m site --user-site)"
mkdir -p $USER_SITE_PACKAGES

### Ardupilot's decoder is used to parse and validate firmware ELF files
COMMIT_HASH=b839ddcc00f4cb89d89aaa8cf0cb03298d2f00b4
LOCAL_PATH_DECODER="${USER_SITE_PACKAGES}/ardupilot_fw_decoder.py"
REMOTE_URL_DECODER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/firmware_version_decoder.py"
wget "$REMOTE_URL_DECODER" -O "$LOCAL_PATH_DECODER"
