#!/usr/bin/env bash
# Script to install tools that needs to configure filesystem of the running docker

# Immediately exit on errors
set -e

TOOLS=(
    ardupilot_tools
    filebrowser
    linux2rest
    logviewer
    mavlink_camera_manager
    scripts
)

parallel --halt now,fail=1 '/home/pi/tools/{}/bootstrap.sh' ::: "${TOOLS[@]}"

# Tools that uses apt to do the installation
# APT is terrible like pip and don't know how to handle parallel installation
/home/pi/tools/cable_guy/bootstrap.sh
/home/pi/tools/dnsmasq/bootstrap.sh
/home/pi/tools/hotspot/bootstrap.sh
/home/pi/tools/iperf3/bootstrap.sh
/home/pi/tools/nginx/bootstrap.sh