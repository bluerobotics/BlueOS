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
# This section is empty as all got moved up to our base image, but this is the
# section where new ones would go if we don't want then in the base image
