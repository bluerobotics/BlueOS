#!/usr/bin/env bash

# Set desired version to be installed
VERSION="${VERSION:-master}"
REMOTE="${REMOTE:-https://raw.githubusercontent.com/bluerobotics/companion-docker}"
REMOTE="$REMOTE/$VERSION"

# Exit immediately if a command exits with a non-zero status
set -e

# Check if the script is running in ARM architecture
[[ "$(uname -m)" != "arm"* ]] && (
    echo "Companion only supports ARM computers."
    exit 1
)

# Check if the script is running as root
[[ $EUID != 0 ]] && echo "Script must run as root."  && exit 1

# Running in a BCM27* or BCM28, do necessary Raspberry configuration
cat /proc/cpuinfo | grep -Eq "BCM(27|28)" && (
    echo "Configuring board.."

    # Remove any configuration related to i2c and spi/spi1 and do the necessary changes for navigator
    echo "- Enable I2C, SPI and UART."
    for STRING in "dtparam=i2c_arm=" "dtparam=spi=" "dtoverlay=spi1" "dtoverlay=uart1"; do
        sudo sed -i "/$STRING/d" /boot/config.txt
    done
    for STRING in "dtparam=i2c_arm=on" "dtparam=spi=on" "dtoverlay=spi1-3cs" "dtoverlay=uart1"; do
        echo "$STRING" | sudo tee -a /boot/config.txt
    done

    # Check for valid modules file to load kernel modules
    if [ -f "/etc/modules" ]; then
        MODULES_FILE="/etc/modules"
    else
        MODULES_FILE="/etc/modules-load.d/companion.conf"
        touch "$MODULES_FILE" || true # Create if it does not exist
    fi

    echo "- Set up kernel modules."
    # Remove any configuration or commented part related to the i2c drive
    for STRING in "bcm2835-v4l2" "i2c-bcm2708" "i2c-dev"; do
        sudo sed -i "/$STRING/d" "$MODULES_FILE"
        echo "$STRING" | sudo tee -a "$MODULES_FILE"
    done

    # Remove any console serial configuration
    echo "- Configure serial."
    sudo sed -e 's/console=serial[0-9],[0-9]*\ //' -i /boot/cmdline.txt
)

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