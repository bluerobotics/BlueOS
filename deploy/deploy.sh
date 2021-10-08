#!/usr/bin/env bash

DEV_DISK=$1
IMAGE_FILE=$2

# function for calling out an error and exiting with error
error() {
    echo -e "ERROR: $*" >&2
    exit 1
}

# function to validate user input
input() {
    read -s -n 1 key
    if [[ $key != $* ]]; then
        echo "User declined to proceed, exiting..."
        exit 0
    fi
}

if [[ $DEV_DISK == "" ]]; then
    echo "usage: ./create-image.sh DISK IMAGEFILE"
    error "no disk argument supplied"
fi

if [[ $IMAGE_FILE == "" ]]; then
    echo "usage: ./create-image.sh DISK IMAGEFILE"
    error "no image argument supplied"
fi

if [[ $3 != "" ]]; then
    echo "usage: ./create-image.sh DISK IMAGEFILE"
    error "too many arguments supplied"
fi

# make sure the disk is on usb
udevadm info $DEV_DISK | grep ID_BUS=usb > /dev/null

if [[ $? != 0 ]]; then
    error "$DEV_DISK is not on the USB bus!"
fi

# TODO make sure the disk contains a companion OS image
# check it is top level disk device, not a partition

# check size
# TODO learn sed/perl/awk w regex
DEV_DISK_SIZE=$(parted -s $DEV_DISK unit GB print devices | grep $DEV_DISK | cut -f2 -d' ')

# make sure the user wants to work with this disk
echo "$DEV_DISK is $DEV_DISK_SIZE"
echo "Are you sure you want to make an image with $DEV_DISK?"
input "y"

MOUNT_LOCATION=/tmp/companion_deploy
mkdir -p $MOUNT_LOCATION

DEV_PART2=$DEV_DISK
DEV_PART2+=2

echo "unmounting $DEV_DISK"
umount $DEV_DISK?*

echo "mounting $DEV_DISK on $MOUNT_LOCATION"
mount $DEV_PART2 $MOUNT_LOCATION || error "Failed to mount $DEV_PART2 on $MOUNT_LOCATION"

cp expand_fs.sh $MOUNT_LOCATION/usr/bin/expand_fs.sh || error "failed to copy expand_fs.sh"

# insert expand_fs command in /etc/rc.local
# above the line to start the companion services
echo "adding expand_fs entry to /etc/rc.local"
EXPAND="/usr/bin/expand_fs.sh"
sed -i "\%$EXPAND%d" $MOUNT_LOCATION/etc/rc.local || error "sed failed to remove expand_fs entry in /etc/rc.local"
sed -i "\%^exit 0%i$EXPAND" $MOUNT_LOCATION/etc/rc.local || error "sed failed to add expand_fs entry in /etc/rc.local"

umount $MOUNT_LOCATION

# check filesystem
e2fsck -n -f $DEV_PART2 || error "e2fsck failed to verify filesystem"

# resize2fs will not run unless e2fsck was run with *only* the -f option
# so we run it again, without the -n (no user input) option
# we assume it won't fail because it did not the first time
e2fsck -f $DEV_PART2 || error "e2fsck failed to verify filesystem"

# shrink filesystem to minimum size
resize2fs -M $DEV_PART2 || error "resize2fs failed to resize partition"

# find new end of filesystem
dumpe2fs $DEV_PART2 -h
BLOCK_COUNT=$(dumpe2fs $DEV_PART2 -h | grep "Block count" | sed 's/[^0-9]*//g')
BLOCK_SIZE=$(dumpe2fs $DEV_PART2 -h | grep "Block size" | sed 's/[^0-9]*//g')
PARTITION_SIZE_BYTES=$(($BLOCK_SIZE * $BLOCK_COUNT))
BEGIN_DATA=$(parted -m $DEV_DISK unit b print | grep ^2: | cut -d: -f2 | tr -d B)
NEW_END=$(($BEGIN_DATA + $PARTITION_SIZE_BYTES))

# shrink partition to match filesystem
# parted -s $DEV_DISK unit b resizepart 2 $NEW_END

# the above command does not work because there is a bug with the --script option
# this workaround was proposed a the thread about the bug here
# https://bugs.launchpad.net/ubuntu/+source/parted/+bug/1270203
echo -e "yes\n" | parted ---pretend-input-tty $DEV_DISK unit b resizepart 2 $NEW_END || error "parted failed to shrink partition"

END_DATA=$(parted -m $DEV_DISK unit MiB print | grep ^2: | cut -d: -f3 | cut -f1 -dM)

echo "The end of the data is $END_DATA MiB"
echo "Do you want to copy $END_DATA MiB from $DEV_DISK to $IMAGE_FILE?"
input "y"

dd if=$DEV_DISK of=$IMAGE_FILE bs=1MiB count=$END_DATA status=progress || error "Failed to copy $DEV_DISK to $IMAGE_FILE"
sync || error "failed to sync"

echo "Do you want to compress $IMAGE_FILE?"
input "y"

zip $IMAGE_FILE.zip $IMAGE_FILE || error "Failed to compress $IMAGE_FILE"

echo "done"
