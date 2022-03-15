#!/usr/bin/env bash

VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/blueos-docker}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
REMOTE="$REMOTE/$VERSION"
CONFIGURE_NETWORK_PATH="$REMOTE/install/network"

# Exit if something goes wrong
set -e

systemctl is-active --quiet avahi-daemon || (
    echo "Avahi daemon is not installed or running."
    exit 1
)

echo "Configuring blueos avahi service"
AVAHI_SERVICE_PATH="/etc/avahi/services"
[ ! -d "${AVAHI_SERVICE_PATH}" ] && (
    echo "Avahi service directory does not exist: ${AVAHI_SERVICE_PATH}"
    exit 1
)
curl -fsSL $CONFIGURE_NETWORK_PATH/blueos.service > "${AVAHI_SERVICE_PATH}/blueos.service"

echo "Configure hostname to blueos"
OLD_HOSTNAME="$(cat /etc/hostname)"
NEW_HOSTNAME="blueos"
# Overwrite with new name
echo $NEW_HOSTNAME > /etc/hostname
# Replace current name
sed -i "s/127.0.1.1.*$OLD_HOSTNAME/127.0.1.1\t$NEW_HOSTNAME/g" /etc/hosts
