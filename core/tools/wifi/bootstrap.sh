#!/usr/bin/env bash

# Immediately exit on errors
set -e

# Wifi service / Bind path for wpa
mkdir -p /var/run/wpa_supplicant/

# Install create_ap script
alias curl="curl --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60"

CREATE_AP_COMMIT="4627e3c0ec0a7c86ba08089a8a00d32a61a05f1e"
CREATE_AP_URL="https://raw.githubusercontent.com/lakinduakash/linux-wifi-hotspot/${CREATE_AP_COMMIT}/src/scripts/create_ap"
CREATE_AP_DEST="/usr/bin/create_ap"

echo "Downloading create_ap script from commit: ${CREATE_AP_COMMIT}"

curl -fsSL "${CREATE_AP_URL}" -o "${CREATE_AP_DEST}"

chmod 755 "${CREATE_AP_DEST}"

echo " - create_ap installed successfully at ${CREATE_AP_DEST}"
