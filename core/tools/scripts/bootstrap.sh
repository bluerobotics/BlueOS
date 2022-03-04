#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

SCRIPTS_PATH=$(dirname "$0")
cp $PWD/$SCRIPTS_PATH/red-pill /usr/bin/
