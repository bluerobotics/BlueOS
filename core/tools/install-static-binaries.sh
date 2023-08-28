#!/usr/bin/env bash
# Script to install tools that are simple static binaries

# Immediately exit on errors
set -e

# Remember to update Dockerfile to copy from multistage
TOOLS=(
    blueos_startup_update
    bridges
    linux2rest
    machineid
    mavlink2rest
    mavlink_router
    mavp2p
    ttyd
)

parallel --halt now,fail=1 'RUNNING_IN_CI=true /home/pi/tools/{}/bootstrap.sh' ::: "${TOOLS[@]}"
