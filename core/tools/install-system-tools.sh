#!/usr/bin/env bash
# Script to install tools that needs to configure filesystem of the running docker

TOOLS=(
    ardupilot_tools
    filebrowser
    linux2rest
    logviewer
    scripts
)

parallel --halt now,fail=1 '/home/pi/tools/{}/bootstrap.sh' ::: "${TOOLS[@]}"

# Tools that uses apt to do the installation
# APT is terrible like pip and don't know how to handle parallel installation
/home/pi/tools/dnsmasq/bootstrap.sh
/home/pi/tools/nginx/bootstrap.sh