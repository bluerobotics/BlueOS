#!/bin/bash

# Grows a mounted ext4 partition on a loop device the way expand_fs.service does on first boot. Needs sudo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
loop=""

cleanup() {
    sudo umount "$tmp/mnt" 2>/dev/null || true
    [ -z "$loop" ] || sudo losetup -d "$loop"
    rm -rf "$tmp"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

fs_bytes() {
    df --output=size -B1 "$tmp/mnt" | tail -n1 | tr -d ' '
}

truncate -s 64M "$tmp/disk.img"
printf 'size=16MiB, type=c\nsize=32MiB, type=83\n' | sfdisk -q "$tmp/disk.img"
loop="$(sudo losetup -fP --show "$tmp/disk.img")"
sudo mkfs.ext4 -q "${loop}p2"
mkdir "$tmp/mnt"
sudo mount "${loop}p2" "$tmp/mnt"
before="$(fs_bytes)"

truncate -s 256M "$tmp/disk.img"
sudo losetup -c "$loop"
sudo "${SCRIPT_DIR}/../expand_fs.sh" "$tmp/mnt"
after="$(fs_bytes)"
[ "$after" -gt $((before + 150 * 1024 * 1024)) ] || fail "filesystem did not grow online: ${before} -> ${after}"

sudo "${SCRIPT_DIR}/../expand_fs.sh" "$tmp/mnt" | grep -q "already fills" || fail "second run should skip the grow"

echo "ok"
