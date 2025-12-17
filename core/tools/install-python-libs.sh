#!/usr/bin/env bash
# Script to install python binaries or single files that should be available within BlueOS python venv

# Immediately exit on errors
set -e

TOOLS=(
    ardupilot_tools
)

TARGET_ENVS=("${BLUEOS_PYTHON_ENVS:-${VIRTUAL_ENV:-}}")

# shellcheck disable=SC2068
for env in ${TARGET_ENVS[@]}; do
    [[ -n $env ]] && export VIRTUAL_ENV="$env" || unset VIRTUAL_ENV
    echo "Installing python tools for ${env:-system python}"
    parallel --halt now,fail=1 '/home/pi/tools/{}/setup-python-libs.sh' ::: "${TOOLS[@]}"
done
