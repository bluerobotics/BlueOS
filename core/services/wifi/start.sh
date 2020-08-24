#!/bin/sh
SERVICE_PATH=$(dirname $(readlink -f "$0"))
python3 $SERVICE_PATH/main.py