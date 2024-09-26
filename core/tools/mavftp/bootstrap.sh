#!/usr/bin/env bash
set -e
# TODO: all of this should be replaced with a single pip install once the pr at pymavlink is merged and there's a new version tagged
mkdir -p /home/pi/tools/mavftp
cd /home/pi/tools/mavftp
apt update && apt install -y git libxml2-dev libxslt-dev build-essential gcc zlib1g-dev
git clone --depth 1 https://github.com/Ardupilot/pymavlink.git
git clone --depth 1 https://github.com/Ardupilot/mavlink.git
cd pymavlink
pip install fusepy==3.0.1 lxml
MDEF="../mavlink/message_definitions" python -m pip install . -v
apt remove -y git build-essential && apt autoremove -y && apt clean -y