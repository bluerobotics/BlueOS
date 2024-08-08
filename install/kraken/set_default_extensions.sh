#!/usr/bin/env bash

# Extensions data fetch, use for Extensions that are synced by some online source

COCKPIT_RELEASE_URL="https://api.github.com/repos/goasChris/cockpit/releases"
MAJOR_TOM_RELEASE_URL="https://blueos.cloud/major_tom/install"

response=$(curl -fsSL $COCKPIT_RELEASE_URL)

if [[ $response =~ \"tag_name\":\ *\"([^\"]+)\" ]]; then
  cockpit_tag_name="${BASH_REMATCH[1]}"
  echo "Using cockpit tag: $cockpit_tag_name"
else
  echo "Could not find the latest release tag of Cockpit."
  exit 1
fi

major_tom_install_data=$(curl -fsSL $MAJOR_TOM_RELEASE_URL)

if [[ $major_tom_install_data =~  \"docker\":\ *\"([^\"]+)\" ]]; then
  major_tom_docker="${BASH_REMATCH[1]}"
else
  echo "Could not find the latest release docker value of Major Tom."
  exit 1
fi

if [[ $major_tom_install_data =~  \"tag\":\ *\"([^\"]+)\" ]]; then
  major_tom_tag="${BASH_REMATCH[1]}"
else
  echo "Could not find the latest release tag value of Major Tom."
  exit 1
fi

echo "Using major tom: $major_tom_docker:$major_tom_tag"

# Images pulling

BLUEROBOTICS_COCKPIT_EXT="goaschris/cockpit:$cockpit_tag_name"
BLUEROBOTICS_MAJOR_TOM_EXT="$major_tom_docker:$major_tom_tag"

docker pull $BLUEROBOTICS_COCKPIT_EXT
docker pull $BLUEROBOTICS_MAJOR_TOM_EXT

# Settings creation

SETTINGS_BASE_DIR="/root/.config/blueos/kraken"

mkdir -p "${SETTINGS_BASE_DIR}"

# Check if the directory creation was successful
if [[ ! -d "${SETTINGS_BASE_DIR}" ]]; then
  echo "Failed to create directory ${SETTINGS_BASE_DIR}"
  exit 1
fi

# Creates kraken V2 settings with default extensions

cat > "${SETTINGS_BASE_DIR}/settings-2.json" <<EOF
{
  "VERSION": 2,
  "extensions": [
    {
      "docker": "goaschris/cockpit",
      "enabled": true,
      "identifier": "goaschris.cockpit",
      "name": "RemoraCockpit",
      "permissions": "{\"ExposedPorts\":{\"8000/tcp\":{}},\"HostConfig\":{\"PortBindings\":{\"8000/tcp\":[{\"HostPort\":\"\"}]}}}",
      "tag": "$cockpit_tag_name",
      "user_permissions": ""
    },
    $major_tom_install_data
  ],
  "manifests": []
}
EOF

echo "Default extensions settings configured successfully."
