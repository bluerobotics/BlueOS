#!/usr/bin/env bash

# Immediately exit on errors
set -e

## Download and install necessary tools to user binary folder with the correct permissions

if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_BIN_DIR="$VIRTUAL_ENV/bin"
else
    PYTHON_BIN_DIR="$(python -m site --user-base)/bin/" || true
fi
mkdir -p "$PYTHON_BIN_DIR"

### Ardupilot's uploader is used to upload firmwares to serial boards
COMMIT_HASH=f6544ca25ab232407ec102b7a5adf0adca0f2062
LOCAL_PATH_UPLOADER="$PYTHON_BIN_DIR/ardupilot_fw_uploader.py"
REMOTE_URL_UPLOADER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/uploader.py"

# Sudo command is not available on docker and the script is also used in different environments
# The SUDO alias allow the usage of sudo when such command exists and also ignore if it doesn't
NOSUDO=${NOSUDO:-0}
if [ -n "$NOSUDO" ]; then
    SUDO=''
else
    SUDO="$(command -v sudo || echo '')"
fi
readonly SUDO
if [ ! -f "$LOCAL_PATH_UPLOADER" ]; then
  $SUDO wget "$REMOTE_URL_UPLOADER" -O "$LOCAL_PATH_UPLOADER"
  $SUDO chmod +x "$LOCAL_PATH_UPLOADER"
else
  echo "File $LOCAL_PATH_UPLOADER already exists. Skipping download."
fi

## Download and install necessary modules to site-packages folder

### Setup site-packages
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_VERSION="$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
    SITE_PACKAGES="$VIRTUAL_ENV/lib/python$PYTHON_VERSION/site-packages"
else
    SITE_PACKAGES="$(python -m site --user-site)" || true
fi
export PYTHONPATH="$SITE_PACKAGES:$PYTHONPATH"
mkdir -p "$SITE_PACKAGES"

### Ardupilot's decoder is used to parse and validate firmware ELF files
COMMIT_HASH=89c2b4828662ece84f48bdf9aa24db688fea36cb
LOCAL_PATH_DECODER="$SITE_PACKAGES/ardupilot_fw_decoder.py"
REMOTE_URL_DECODER="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/firmware_version_decoder.py"
if [ ! -f "$LOCAL_PATH_DECODER" ]; then
    wget "$REMOTE_URL_DECODER" -O "$LOCAL_PATH_DECODER"
else
    echo "File $LOCAL_PATH_DECODER already exists. Skipping download."
fi


### Ardupilot's apj_tool is used to embed params into apj files
COMMIT_HASH=b839ddcc00f4cb89d89aaa8cf0cb03298d2f00b4
LOCAL_PATH_APJ_TOOL="$PYTHON_BIN_DIR/apj_tool.py"
REMOTE_URL_APJ_TOOL="https://raw.githubusercontent.com/ArduPilot/ardupilot/${COMMIT_HASH}/Tools/scripts/apj_tool.py"
if [ ! -f "$LOCAL_PATH_APJ_TOOL" ]; then
    $SUDO wget "$REMOTE_URL_APJ_TOOL" -O "$LOCAL_PATH_APJ_TOOL"
    $SUDO chmod +x "$LOCAL_PATH_APJ_TOOL"
else
    echo "File $LOCAL_PATH_APJ_TOOL already exists. Skipping download."
fi

# Create the logs folder before ardupilot so we prevent a Filebrowser error if the user opens it
# before arming the vehicle for the first time.
if [ -z "$NOSUDO" ]; then
    $SUDO mkdir -p /root/.config/ardupilot-manager/firmware/logs/
fi
