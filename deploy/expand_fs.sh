#!/bin/sh

# Grows the partition holding / to the end of its disk and resizes the filesystem, online and without a reboot.
# An optional argument grows the filesystem mounted there instead of /.

set -e

MOUNT_POINT="${1:-/}"
PART_SYS=$(readlink -f "/sys/dev/block/$(findmnt -n -r -o MAJ:MIN -T "$MOUNT_POINT")")
DISK_SYS=$(dirname "$PART_SYS")
if [ ! -f "$PART_SYS/partition" ]; then
    echo "$MOUNT_POINT is not on a disk partition, can't expand it"
    exit 1
fi
PART_NUM=$(cat "$PART_SYS/partition")
PART_DEV="/dev/$(basename "$PART_SYS")"
DISK_DEV="/dev/$(basename "$DISK_SYS")"
# sysfs sizes are always in 512-byte sectors
FREE_SECTORS=$(($(cat "$DISK_SYS/size") - $(cat "$PART_SYS/start") - $(cat "$PART_SYS/size")))

# sfdisk may round the new end down to 1 MiB, so less than that left over means it is already full size
if [ "$FREE_SECTORS" -ge 2048 ]; then
    echo "Growing $PART_DEV into $FREE_SECTORS free sectors on $DISK_DEV"
    # --no-reread skips the in-use check that refuses a disk with a mounted partition
    echo ", +" | sfdisk --no-reread --no-tell-kernel --wipe never --wipe-partitions never -N "$PART_NUM" "$DISK_DEV"
    # sfdisk skips its fsync here, and the table must be on disk before the filesystem grows past the old end
    sync
    partx -u --nr "$PART_NUM" "$DISK_DEV"
else
    echo "$PART_DEV already fills $DISK_DEV"
fi

resize2fs "$PART_DEV"

if [ -f /etc/rc.local ]; then
    sed -i '\%/usr/bin/expand_fs.sh%d' /etc/rc.local
fi
