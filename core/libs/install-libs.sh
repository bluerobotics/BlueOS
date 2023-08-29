#!/usr/bin/env bash

# Immediately exit on errors
set -e

CURRENT_PATH=$(dirname "$0")

# Install libraries
python3 $CURRENT_PATH/bridges/setup.py install
python3 $CURRENT_PATH/commonwealth/setup.py install
