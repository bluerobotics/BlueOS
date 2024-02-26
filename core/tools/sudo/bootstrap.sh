#!/usr/bin/env bash

# Exit if something goes wrong
set -e

echo "Installing sudo."
apt update
apt install --no-install-recommends --no-install-suggests -y sudo
