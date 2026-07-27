#!/usr/bin/env bash

set -e

VERSION="4.8"
SHA256="33ea8eb2a4daeaa506e8fcafd5d6d89027ed6f2f0609645c6f149b560d301706"
PROJECT_NAME="chrony"
SOURCE_URL="https://chrony-project.org/releases/$PROJECT_NAME-$VERSION.tar.gz"

echo "Installing project $PROJECT_NAME version $VERSION"

if [ -z "$RUNNING_IN_CI" ]; then
    mkdir -p /run/chrony
    echo "Finished configuring $PROJECT_NAME"
    exit 0
fi

if [ -n "$VIRTUAL_ENV" ]; then
    BIN_DIR="$VIRTUAL_ENV/bin"
else
    BIN_DIR="/usr/bin"
fi
mkdir -p "$BIN_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

ARCHIVE="$TMP_DIR/$PROJECT_NAME-$VERSION.tar.gz"
wget -q "$SOURCE_URL" -O "$ARCHIVE"
printf "%s  %s\n" "$SHA256" "$ARCHIVE" | sha256sum -c -

tar -xzf "$ARCHIVE" -C "$TMP_DIR"
cd "$TMP_DIR/$PROJECT_NAME-$VERSION"

LDFLAGS="${LDFLAGS:-} -static" ./configure \
    --prefix=/usr \
    --bindir=/usr/bin \
    --sbindir=/usr/bin \
    --sysconfdir=/etc \
    --localstatedir=/var \
    --chronyrundir=/run/chrony \
    --chronyvardir=/usr/blueos/userdata/chrony \
    --disable-nts \
    --disable-privdrop \
    --disable-readline \
    --disable-sechash \
    --with-chronyc-user=root \
    --with-user=root \
    --without-libcap \
    --without-seccomp

make -j"$(nproc)" chronyd chronyc
strip chronyd chronyc
install -m 0755 chronyd "$BIN_DIR/chronyd"
install -m 0755 chronyc "$BIN_DIR/chronyc"

if command -v file >/dev/null 2>&1; then
    echo "Installed binary type: $(file "$BIN_DIR/chronyd")"
    echo "Installed binary type: $(file "$BIN_DIR/chronyc")"
fi

echo "Finished installing $PROJECT_NAME"
