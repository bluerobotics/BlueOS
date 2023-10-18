#!/usr/bin/env bash

# Exit if something goes wrong
set -e

echo "Installing iperf3."
apt update
apt install --no-install-recommends --no-install-suggests -y iperf3
