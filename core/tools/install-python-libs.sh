#!/usr/bin/env bash
# Script to install python binaries or single files that should be available within BlueOS python venv

# Immediately exit on errors
set -e

TOOLS=(
    ardupilot_tools
)

parallel --halt now,fail=1 '/home/pi/tools/{}/setup-python-libs.sh' ::: "${TOOLS[@]}"
