#!/usr/bin/env bash

VERSION="${VERSION:-master}"
REMOTE="${REMOTE:-https://raw.githubusercontent.com/bluerobotics/companion-docker}"
REMOTE="$REMOTE/$VERSION"
CONFIGURE_NETWORK_PATH="$REMOTE/install/network"

# Exit if something goes wrong
set -e

systemctl is-active --quiet avahi-daemon || (
    echo "Avahi daemon is installed and running."
    exit 1
)

echo "Configuring companion avahi service"
AVAHI_SERVICE_PATH="/etc/avahi/services"
[ ! -d "${AVAHI_SERVICE_PATH}" ] && (
    echo "Avahi service directory does not exist: ${AVAHI_SERVICE_PATH}"
    exit 1
)
curl -fsSL $CONFIGURE_NETWORK_PATH/companion.service > "${AVAHI_SERVICE_PATH}/companion.service"

echo "Configure hostname to companion"
OLD_HOSTNAME="$(cat /etc/hostname)"
NEW_HOSTNAME="companion"
# Overwrite with new name
echo $NEW_HOSTNAME > /etc/hostname
# Replace current name
sed -i "s/127.0.1.1.*$OLD_HOSTNAME/127.0.1.1\t$NEW_HOSTNAME/g" /etc/hosts