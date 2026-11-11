#!/usr/bin/env bash

# Immediately exit on errors
set -e

PROJECT_NAME="swagger_ui"
SWAGGER_UI_VERSION="5.34.0"
SWAGGER_UI_JS_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@$SWAGGER_UI_VERSION/swagger-ui-bundle.js"
SWAGGER_UI_CSS_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@$SWAGGER_UI_VERSION/swagger-ui.css"
REDOC_VERSION="2.5.4"
REDOC_JS_URL="https://cdn.jsdelivr.net/npm/redoc@$REDOC_VERSION/bundles/redoc.standalone.js"

echo "Installing project $PROJECT_NAME"

# Step 1: Prepare the installation path

STATIC_FOLDER="/usr/blueos/static"
mkdir -p "$STATIC_FOLDER"
echo "Installing to $STATIC_FOLDER"

# Step 2: Download and install

alias curl="curl --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60"

shopt -s expand_aliases

curl -fsSL "$SWAGGER_UI_JS_URL" -o "$STATIC_FOLDER/swagger-ui-bundle.js"
curl -fsSL "$SWAGGER_UI_CSS_URL" -o "$STATIC_FOLDER/swagger-ui.css"
curl -fsSL "$REDOC_JS_URL" -o "$STATIC_FOLDER/redoc.standalone.js"

echo "Finished installing $PROJECT_NAME"
