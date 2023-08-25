#!/usr/bin/env bash

# Immediately exit on errors
set -e

## Download and install necessary tools to user binary folder with the correct permissions

### Ardupilot's uploader is used to upload firmwares to serial boards
COMMIT_HASH=f6544ca25ab232407ec102b7a5adf0adca0f2062
LOCAL_PATH_UPLOADER="$(python -m site --user-base)/bin/ardupilot_fw_uploader.py" || true
mkdir -p "$(python -m site --user-base)/bin"
REMOTE_URL_UPLOADER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/uploader.py"

# Sudo command is not available on docker and the script is also used in different environments
# The SUDO alias allow the usage of sudo when such command exists and also ignore if it doesn't
SUDO="$(command -v sudo || echo '')"
readonly SUDO
if [ ! -f "$LOCAL_PATH_UPLOADER" ]; then
  $SUDO wget "$REMOTE_URL_UPLOADER" -O "$LOCAL_PATH_UPLOADER"
  $SUDO chmod +x "$LOCAL_PATH_UPLOADER"
else
  echo "File $LOCAL_PATH_UPLOADER already exists. Skipping download."
fi
## Download and install necessary modules to user-site folder

# Check if pipenv is installed
if command -v pipenv &> /dev/null; then
    VERSION="$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
    USER_SITE_PACKAGES="$(pipenv --venv)/lib/python${VERSION}/site-packages/"
else
    # Fall back to the global Python site-packages directory if pipenv is not installed
    USER_SITE_PACKAGES="$(python -m site --user-site)"
fi
mkdir -p $USER_SITE_PACKAGES

### Ardupilot's decoder is used to parse and validate firmware ELF files
COMMIT_HASH=b839ddcc00f4cb89d89aaa8cf0cb03298d2f00b4
LOCAL_PATH_DECODER="${USER_SITE_PACKAGES}/ardupilot_fw_decoder.py" || true
REMOTE_URL_DECODER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/firmware_version_decoder.py"
if [ ! -f "$LOCAL_PATH_DECODER" ]; then
    wget "$REMOTE_URL_DECODER" -O "$LOCAL_PATH_DECODER"
else
    echo "File $LOCAL_PATH_DECODER already exists. Skipping download."
fi


### Ardupilot's apj_tool is used to embed params into apj files
COMMIT_HASH=b839ddcc00f4cb89d89aaa8cf0cb03298d2f00b4
LOCAL_PATH_APJ_TOOL="$(python -m site --user-base)/bin/apj_tool.py" || true
REMOTE_URL_APJ_TOOL="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/apj_tool.py"
if [ ! -f "$LOCAL_PATH_APJ_TOOL" ]; then
    $SUDO wget "$REMOTE_URL_APJ_TOOL" -O "$LOCAL_PATH_APJ_TOOL"
    $SUDO chmod +x "$LOCAL_PATH_APJ_TOOL"
else
    echo "File $LOCAL_PATH_APJ_TOOL already exists. Skipping download."
fi

# Create the logs folder before ardupilot so we prevent a Filebrowser error if the user opens it
# before arming the vehicle for the first time.
$SUDO mkdir -p /root/.config/ardupilot-manager/firmware/logs/