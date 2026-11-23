#!/usr/bin/env bash
# Script to install tools that needs to configure filesystem of the running docker

# Immediately exit on errors
set -e

# Keep in sync with the tools copied by the "install-system-tools" step in the Dockerfile.
TOOLS=(
    ardupilot_tools
    filebrowser
    logviewer
    scripts
    swagger_ui
    wifi
)

parallel --halt now,fail=1 '/home/pi/tools/{}/bootstrap.sh' ::: "${TOOLS[@]}"

# wget records the time of each download here, which would make this layer differ on every build
rm -f "$HOME/.wget-hsts"

# Tools that uses apt to do the installation
# APT is terrible like pip and don't know how to handle parallel installation
# These should periodically be moved onto the base image

# apt update && apt install -y --no-install-recommends [your latest forgotten packages here]
# clean && rm -rf /var/lib/apt/lists/*
