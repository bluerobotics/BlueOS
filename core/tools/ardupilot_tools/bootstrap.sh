#!/usr/bin/env bash

# Immediately exit on errors
set -e

# Create the logs folder before ardupilot so we prevent a Filebrowser error if the user opens it
# before arming the vehicle for the first time.
if [ -z "$NOSUDO" ]; then
    $SUDO mkdir -p /root/.config/ardupilot-manager/firmware/logs/
fi

# Download firmware defaults
AUTOPILOT_DEFAULT_FIRMWARE_PATH="$HOME/blueos-files/ardupilot-manager/default"

download_if_not_exists() {
    local url=$1
    local dest=$2

    if [ ! -f "$dest" ]; then
        echo "Downloading $url to $dest"
        mkdir -p "$(dirname "$dest")"
        wget -q "$url" -O "$dest" && echo "Downloaded $dest" &
    else
        echo "File $dest already exists. Skipping download."
    fi
}

download_if_not_exists "https://firmware.ardupilot.org/Sub/stable-4.5.3/navigator/ardusub" \
                       "$AUTOPILOT_DEFAULT_FIRMWARE_PATH/ardupilot_navigator/ardusub"

download_if_not_exists "https://firmware.ardupilot.org/Sub/stable-4.5.3/navigator64/ardusub" \
                       "$AUTOPILOT_DEFAULT_FIRMWARE_PATH/ardupilot_navigator64/ardusub"

download_if_not_exists "https://firmware.ardupilot.org/Sub/stable-4.5.3/Pixhawk1/ardusub.apj" \
                       "$AUTOPILOT_DEFAULT_FIRMWARE_PATH/ardupilot_pixhawk1/ardusub.apj"

download_if_not_exists "https://firmware.ardupilot.org/Sub/stable-4.5.3/Pixhawk4/ardusub.apj" \
                       "$AUTOPILOT_DEFAULT_FIRMWARE_PATH/ardupilot_pixhawk4/ardusub.apj"

# Wait for all background jobs to finish
wait
echo "All downloads completed."
