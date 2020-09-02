#!/usr/bin/env bash

# Set desired version to be installed
VERSION="${VERSION:-master}"
REMOTE="${REMOTE:-https://raw.githubusercontent.com/bluerobotics/companion-docker}"
REMOTE="$REMOTE/$VERSION"

# Exit immediately if a command exits with a non-zero status
set -e

# Check if the script is running in ARM architecture
[[ "$(uname -m)" != "arm"* ]] && echo "Companion only supports ARM computers."

# Check if the script is running as root
[[ $EUID != 0 ]] && echo "Script must run as root."  && exit 1

echo "Checking for blocked wifi and bluetooth."
rfkill unblock all

# Check for docker and install it if not found
echo "Checking for docker."
docker --version || curl -fsSL https://get.docker.com | sh && systemctl enable docker

# Stop and remove all docker if NO_CLEAN is not defined
test $NO_CLEAN || (
    # Check if there is any docker installed
    [[ $(docker ps -a -q) ]] && (
        echo "Stopping running dockers."
        docker stop $(docker ps -a -q)

        echo "Removing dockers."
        docker rm $(docker ps -a -q)
    ) || true
)

# Start installing necessary files and system configuration
echo "Going to install companion-docker version ${VERSION}."

echo "Downloading and installing udev rules."
curl -fsSL $REMOTE/install/udev/100.autopilot.rules -o /etc/udev/rules.d/100.autopilot.rules

echo "Downloading companion-core"
COMPANION_CORE="bluerobotics/companion-core:master" # We don't have others tags for now
docker pull $COMPANION_CORE
docker create \
    --restart unless-stopped \
    --name companion-core \
    --privileged \
    --network host \
    -v /dev:/dev \
    -v /tmp/wpa_playground:/tmp/wpa_playground \
    -v /var/run/wpa_supplicant/wlan0:/var/run/wpa_supplicant/wlan0 \
    $COMPANION_CORE
# Start companion-core for the first time to allow docker to restart it after reboot
docker start companion-core

echo "Installation finished successfully."
echo "System will reboot in 10 seconds."
sleep 10 && reboot