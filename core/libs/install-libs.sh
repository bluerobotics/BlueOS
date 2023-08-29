#!/usr/bin/env bash

# Immediately exit on errors
set -e

# Pre-Build dependencies:
# For convenience, we build ourselves the .wheel packages for dependencies
# which have no armv7 wheel in pypi. This saves a lot of build time in docker
if [[ "$(uname -m)" == "armv7l"* ]]; then
    pip install https://s3.amazonaws.com/downloads.bluerobotics.com/companion-docker/wheels/aiohttp-3.7.4-cp39-cp39-linux_armv7l.whl
fi

CURRENT_PATH=$(dirname "$0")

# Install libraries
python3 $CURRENT_PATH/bridges/setup.py install
python3 $CURRENT_PATH/commonwealth/setup.py install
