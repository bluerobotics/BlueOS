#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

SCRIPTS_PATH=$(dirname "$0")
cp $PWD/$SCRIPTS_PATH/blueos_startup_update.py /usr/bin/
