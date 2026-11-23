#!/usr/bin/env bash

set -euo pipefail

DATABASE_PATH="/etc/filebrowser/filebrowser.db"

# The database holds random keys and salts, so it is created here and not at build time: a build step that
# writes it never produces the same layer twice, and every vehicle would share the same key. It is built at a
# temporary path and moved into place only when both steps worked, so a failed start leaves no half-made database.
if [ ! -f "$DATABASE_PATH" ]; then
    mkdir -p "$(dirname "$DATABASE_PATH")"
    TMP_DATABASE_PATH="$DATABASE_PATH.tmp"
    rm -f "$TMP_DATABASE_PATH"
    if filebrowser config init --address=0.0.0.0 --port=7777 --auth.method=noauth --log=stdout --root=/shortcuts \
        --database="$TMP_DATABASE_PATH" \
        && filebrowser users add pi raspberry --database="$TMP_DATABASE_PATH"; then
        mv "$TMP_DATABASE_PATH" "$DATABASE_PATH"
    else
        rm -f "$TMP_DATABASE_PATH"
        exit 1
    fi
fi

exec filebrowser --database "$DATABASE_PATH" --baseurl /file-browser
