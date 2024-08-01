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
# this is the section where apt stuff gets installed until we move them up to
# blueos-base

apt update
apt install -y --no-install-recommends fuse libfuse2
apt clean
rm -rf /var/lib/apt/lists/*
