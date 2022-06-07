#!/usr/bin/env bash
# Script to install tools that are simple static binaries

# Immediately exit on errors
set -e

TOOLS=(
    bridges
    linux2rest
    mavlink2rest
    mavlink_router
    ttyd
)

parallel --halt now,fail=1 '/home/pi/tools/{}/bootstrap.sh' ::: "${TOOLS[@]}"
