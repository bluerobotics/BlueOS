#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

SCRIPTS_PATH="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
cp $SCRIPTS_PATH/red-pill /usr/bin/
