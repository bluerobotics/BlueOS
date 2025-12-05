#!/usr/bin/env bash
# Script to install python binaries or single files that should be available within BlueOS python venv

# Immediately exit on errors
set -e

TOOLS=(
    ardupilot_tools
)

determine_target_envs() {
    if [ -n "$BLUEOS_PYTHON_ENVS" ]; then
        read -r -a TARGET_ENVS <<< "$BLUEOS_PYTHON_ENVS"
    elif [ -n "$VIRTUAL_ENV" ]; then
        TARGET_ENVS=("$VIRTUAL_ENV")
    else
        TARGET_ENVS=("")
    fi
}

install_for_env() {
    local target_env="$1"

    if [ -n "$target_env" ]; then
        export VIRTUAL_ENV="$target_env"
        echo "Installing python tools for virtualenv: $target_env"
    else
        unset VIRTUAL_ENV
        echo "Installing python tools for system python"
    fi

    parallel --halt now,fail=1 '/home/pi/tools/{}/setup-python-libs.sh' ::: "${TOOLS[@]}"
}

determine_target_envs

for env_path in "${TARGET_ENVS[@]}"; do
    install_for_env "$env_path"
done
