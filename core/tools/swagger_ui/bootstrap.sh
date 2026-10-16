#!/usr/bin/env bash

# Immediately exit on errors
set -e

PROJECT_NAME="swagger_ui"

echo "Installing project $PROJECT_NAME"

SWAGGER_UI_JS_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
SWAGGER_UI_CSS_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
REDOC_JS_URL="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js"

# Prepare the installation path

STATIC_FOLDER="/usr/blueos/static"
mkdir -p "$STATIC_FOLDER"

echo "Installing to $STATIC_FOLDER"

# Download and install

curl -fsSL --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60 \
    "$SWAGGER_UI_JS_URL" -o "$STATIC_FOLDER/swagger-ui-bundle.js"
curl -fsSL --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60 \
    "$SWAGGER_UI_CSS_URL" -o "$STATIC_FOLDER/swagger-ui.css"
curl -fsSL --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60 \
    "$REDOC_JS_URL" -o "$STATIC_FOLDER/redoc.standalone.js"

echo "Finished installing $PROJECT_NAME"
