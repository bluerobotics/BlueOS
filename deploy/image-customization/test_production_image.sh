#!/bin/bash

# Offline grow, --size parsing and identity sanitizing used for production images. Needs sudo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/customize_images.sh"

tmp="$(mktemp -d)"
loop=""
mnt=""

cleanup() {
    [ -z "$mnt" ] || sudo umount "$mnt"
    [ -z "$loop" ] || sudo losetup -d "$loop"
    # sanitize_identity leaves root-owned links and dirs behind
    sudo rm -rf "$tmp"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

block_count() {
    sudo dumpe2fs -h "${loop}p2" 2>/dev/null | awk -F: '/^Block count/ { gsub(/ /, "", $2); print $2 }'
}

[ "$(parse_image_size 113G)" = "121332826112" ] || fail "113G parsed as $(parse_image_size 113G)"
[ "$(parse_image_size 121782665216)" = "121782665216" ] || fail "plain bytes changed"
[ "$(parse_image_size $((64 * 1048576 + 4095)))" = "$((64 * 1048576))" ] || fail "not rounded down to 1 MiB"
if (parse_image_size 32M $((64 * 1048576))) 2>/dev/null; then
    fail "size smaller than the image accepted"
fi
if (parse_image_size bogus) 2>/dev/null; then
    fail "invalid size accepted"
fi

img="$tmp/disk.img"
truncate -s 64M "$img"
printf 'label: dos\nlabel-id: 0x1234abcd\nsize=16MiB, type=c\nsize=32MiB, type=83\n' | sfdisk -q "$img"
loop="$(sudo losetup -fP --show "$img")"
sudo mkfs.ext4 -q "${loop}p2"
before="$(block_count)"
sudo losetup -d "$loop"
loop=""

grow_image_offline "$img" "$(parse_image_size 128M)" >/dev/null
[ "$(stat -c %s "$img")" = "134217728" ] || fail "image size $(stat -c %s "$img")"
[ "$(sfdisk --disk-id "$img")" = "0x1234abcd" ] || fail "disk identifier changed to $(sfdisk --disk-id "$img")"
p2_end="$(sfdisk -J "$img" | jq '.partitiontable.partitions[1] | .start + .size')"
[ "$p2_end" = "$((134217728 / 512))" ] || fail "p2 ends at sector ${p2_end}"

loop="$(sudo losetup -fP --show "$img")"
resize_rootfs_offline "${loop}p2" >/dev/null 2>&1
after="$(block_count)"
[ "$after" -gt "$before" ] || fail "filesystem did not grow: ${before} -> ${after} blocks"

rootfs="$tmp/rootfs"
mkdir -p "$rootfs"/{etc/ssh,etc/wpa_supplicant,var/lib/dbus,var/lib/docker/containers/abc,var/lib/systemd} \
    "$rootfs"/{var/lib/dhcpcd,lib/systemd/system,root/.config/blueos/.ssh,home/pi/.ssh,tmp/dir,var/tmp}
echo "0123456789abcdef0123456789abcdef" | tee "$rootfs/etc/machine-id" >"$rootfs/var/lib/dbus/machine-id"
touch "$rootfs/etc/ssh/ssh_host_ed25519_key" "$rootfs/etc/ssh/ssh_host_ed25519_key.pub" "$rootfs/etc/ssh/sshd_config"
touch "$rootfs/lib/systemd/system/regenerate_ssh_host_keys.service" "$rootfs/etc/wpa_supplicant/wpa_supplicant.conf"
echo "id" >"$rootfs/var/lib/docker/engine-id"
echo '{"log":"x"}' >"$rootfs/var/lib/docker/containers/abc/abc-json.log"
echo "private" >"$rootfs/root/.config/blueos/.ssh/id_rsa"
echo "ssh-rsa AAAAcorekey root@blueos" >"$rootfs/root/.config/blueos/.ssh/id_rsa.pub"
printf 'ssh-ed25519 AAAAshipped factory\nssh-rsa AAAAcorekey root@blueos\n' >"$rootfs/home/pi/.ssh/authorized_keys"
touch "$rootfs/var/lib/systemd/random-seed" "$rootfs/var/lib/dhcpcd/wlan0.lease" "$rootfs/root/.bash_history" \
    "$rootfs/home/pi/.bash_history" "$rootfs/tmp/junk" "$rootfs/tmp/dir/x" "$rootfs/var/tmp/y"

sanitize_identity "$rootfs" >/dev/null
[ "$(cat "$rootfs/etc/machine-id")" = "uninitialized" ] || fail "machine-id not reset"
[ "$(readlink "$rootfs/var/lib/dbus/machine-id")" = "/etc/machine-id" ] || fail "dbus machine-id is not a link"
[ -z "$(ls "$rootfs"/etc/ssh/ssh_host_* 2>/dev/null)" ] || fail "ssh host keys left"
[ -f "$rootfs/etc/ssh/sshd_config" ] || fail "sshd_config removed"
[ "$(readlink "$rootfs/etc/systemd/system/multi-user.target.wants/regenerate_ssh_host_keys.service")" \
    = "/lib/systemd/system/regenerate_ssh_host_keys.service" ] || fail "regenerate_ssh_host_keys not enabled"
[ ! -e "$rootfs/var/lib/docker/engine-id" ] || fail "engine-id left"
[ ! -s "$rootfs/var/lib/docker/containers/abc/abc-json.log" ] || fail "container log not truncated"
[ ! -e "$rootfs/root/.config/blueos/.ssh/id_rsa" ] || fail "core id_rsa left"
[ ! -e "$rootfs/root/.config/blueos/.ssh/id_rsa.pub" ] || fail "core id_rsa.pub left"
[ "$(cat "$rootfs/home/pi/.ssh/authorized_keys")" = "ssh-ed25519 AAAAshipped factory" ] \
    || fail "authorized_keys should only lose the core key"
for f in var/lib/systemd/random-seed var/lib/dhcpcd/wlan0.lease root/.bash_history home/pi/.bash_history; do
    [ ! -e "$rootfs/$f" ] || fail "$f left"
done
for d in tmp var/tmp; do
    [ -d "$rootfs/$d" ] || fail "$d removed"
    [ -z "$(ls -A "$rootfs/$d")" ] || fail "$d not emptied"
done
[ -f "$rootfs/etc/wpa_supplicant/wpa_supplicant.conf" ] || fail "wpa_supplicant.conf removed"
[ -z "$(sanitize_identity "$rootfs")" ] || fail "second run still found something"

echo "ssh-rsa AAAAcorekey root@blueos" >"$rootfs/root/.config/blueos/.ssh/id_rsa.pub"
echo "ssh-rsa AAAAcorekey root@blueos" >"$rootfs/home/pi/.ssh/authorized_keys"
sanitize_identity "$rootfs" >/dev/null
[ ! -e "$rootfs/home/pi/.ssh/authorized_keys" ] || fail "authorized_keys with only the core key left"

# swapon needs a real filesystem: no holes, no unwritten extents
sudo losetup -d "$loop"
loop=""
truncate -s 64M "$tmp/swapfs.img"
mkfs.ext4 -q -F "$tmp/swapfs.img"
mnt="$tmp/swapfs"
mkdir -p "$mnt"
sudo mount -o loop "$tmp/swapfs.img" "$mnt"
sudo chown "$(id -u):$(id -g)" "$mnt"
mkdir -p "$mnt"/{etc/systemd/system/multi-user.target.wants,sbin,lib/systemd/system,var,boot}
touch "$mnt/sbin/dphys-swapfile" "$mnt/lib/systemd/system/dphys-swapfile.service"
ln -s /lib/systemd/system/dphys-swapfile.service "$mnt/etc/systemd/system/multi-user.target.wants/"
note1="# a swapfile is not a swap partition, no line here"
note2="#   use  dphys-swapfile swap[on|off]  for that"
printf 'proc /proc proc defaults 0 0\n%s\n/dev/x / ext4 defaults 0 1\n' "$note1" >"$mnt/etc/fstab"
printf '#CONF_SWAPSIZE=100\nCONF_SWAPSIZE=2\n  CONF_SWAPSIZE="8" # absolute\nCONF_MAXSWAP=4\n' >"$mnt/etc/dphys-swapfile"
swap="$mnt/var/swap"

prepare_swapfile "$mnt" >/dev/null
prepare_swapfile "$mnt" >/dev/null
[ "$(sudo stat -c %s "$swap")" = "4194304" ] || fail "swap file is $(sudo stat -c %s "$swap") bytes"
read -r nblocks bsize < <(sudo stat -c '%b %B' "$swap")
[ $((nblocks * bsize)) -ge 4194304 ] || fail "swap file has holes"
! sudo filefrag -v "$swap" | grep -q unwritten || fail "swap file has unwritten extents"
[ "$(sudo blkid -p -o value -s TYPE "$swap")" = "swap" ] || fail "no swap signature"
[ "$(sudo stat -c '%a %U:%G' "$swap")" = "600 root:root" ] || fail "swap file is $(sudo stat -c '%a %U:%G' "$swap")"
[ "$(grep -cxF "$note1" "$mnt/etc/fstab")" = "1" ] && [ "$(grep -cxF "$note2" "$mnt/etc/fstab")" = "1" ] \
    || fail "fstab notes not exactly once"
[ "$(tail -n 2 "$mnt/etc/fstab")" = "$(printf '%s\n%s' "$note1" "$note2")" ] || fail "fstab notes not at the end"
grep -qxF "/dev/x / ext4 defaults 0 1" "$mnt/etc/fstab" || fail "fstab lost an entry"

# unlimited CONF_MAXSWAP, 40 MiB needs 80 MiB free
printf 'CONF_SWAPSIZE=40\nCONF_MAXSWAP=\n' >"$mnt/etc/dphys-swapfile"
if (prepare_swapfile "$mnt") >/dev/null 2>&1; then
    fail "swap file larger than half the free space accepted"
fi

sudo rm -f "$swap"
printf 'CONF_SWAPSIZE=\n' >"$mnt/etc/dphys-swapfile"
prepare_swapfile "$mnt" >/dev/null
[ ! -e "$swap" ] || fail "swap file created without CONF_SWAPSIZE"

printf 'CONF_SWAPSIZE=4\n' >"$mnt/etc/dphys-swapfile"
touch "$mnt/boot/kernel_2712.img"
prepare_swapfile "$mnt" >/dev/null
[ ! -e "$swap" ] || fail "swap file created for a 16 KiB page kernel"

echo "ok"
