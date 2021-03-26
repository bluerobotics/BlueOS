#!/usr/bin/env bash

# Set desired version to be installed
VERSION="${VERSION:-master}"
REMOTE="${REMOTE:-https://raw.githubusercontent.com/bluerobotics/companion-docker}"
ROOT="$REMOTE/$VERSION"

# Exit immediately if a command exits with a non-zero status
set -e

# Check if the script is running in ARM architecture
[[ "$(uname -m)" != "arm"* ]] && (
    echo "Companion only supports ARM computers."
    exit 1
)

# Check if the script is running as root
[[ $EUID != 0 ]] && echo "Script must run as root."  && exit 1

echo "Checking if network and remote are available."
curl -fsSL --silent $ROOT/install/install.sh 1> /dev/null || (
    echo "Remote is not available: ${ROOT}"
    exit 1
)

# Detect CPU and do necessary hardware configuration for each supported hardware
echo "Starting hardware configuration."
echo "$ROOT/install/boards/configure_board.sh"
curl -fsSL "$ROOT/install/boards/configure_board.sh" | bash

echo "Checking for blocked wifi and bluetooth."
rfkill unblock all

# Get the number of free blocks and the block size in bytes, and calculate the value in GB
echo "Checking for available space."
AVAILABLE_SPACE_GB=$(($(stat -f / --format="%a*%S/1024**3")))
NECESSARY_SPACE_GB=4
(( AVAILABLE_SPACE_GB < NECESSARY_SPACE_GB )) && (
    echo "Not enough free space to install companion, at least ${NECESSARY_SPACE_GB}GB required"
    exit 1
)

# Check for docker and install it if not found
echo "Checking for docker."
docker --version || curl -fsSL https://get.docker.com | sh || (
    echo "Failed to start docker, something is wrong."
    echo "Please report this problem."
    exit 1
)
systemctl enable docker

# Stop and remove all docker if NO_CLEAN is not defined
test $NO_CLEAN || (
    # Check if there is any docker installed
    [[ $(docker ps -a -q) ]] && (
        echo "Stopping running dockers."
        docker stop $(docker ps -a -q)

        echo "Removing dockers."
        docker rm $(docker ps -a -q)
        docker image prune -af
    ) || true
)

# Start installing necessary files and system configuration
echo "Going to install companion-docker version ${VERSION}."

echo "Downloading and installing udev rules."
curl -fsSL $ROOT/install/udev/100.autopilot.rules -o /etc/udev/rules.d/100.autopilot.rules

echo "Downloading bootstrap"
COMPANION_BOOTSTRAP="bluerobotics/companion-bootstrap:master" # We don't have others tags for now
docker pull $COMPANION_BOOTSTRAP
# Start bootstrap for the first time to fetch the other images and allow docker to restart it after reboot
docker run \
    -t \
    --restart unless-stopped \
    --name companion-bootstrap \
    -v $HOME/.config/companion/bootstrap:/root/.config/bootstrap \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e COMPANION_CONFIG_PATH=$HOME/.config/companion \
    $COMPANION_BOOTSTRAP

# Configure network settings
## This should be after everything, otherwise network problems can happen
echo "Starting network configuration."
curl -fsSL $ROOT/install/network/avahi.sh | bash

echo "Installation finished successfully."
echo "System will reboot in 10 seconds."
sleep 10 && reboot