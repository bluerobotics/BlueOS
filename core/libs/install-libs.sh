#!/usr/bin/env bash

# Immediately exist on errors
set -e

# Commonwealth library:
cd /home/pi/libs/commonwealth/ && python3 setup.py install
