#!/usr/bin/env bash
FILE=raspios_lite_armhf-2021-11-08/2021-10-30-raspios-bullseye-armhf-lite.zip
FILENAME=$(basename $FILE)
FILENAME_PREFIX=${FILENAME%.*}

echo "Downloading image: $FILENAME"
wget --no-clobber https://downloads.raspberrypi.org/raspios_lite_armhf/images/$FILE
unzip -n $FILENAME

echo "Clone linux source code"
git clone --depth 1  --branch rpi-4.19.y https://github.com/raspberrypi/linux

echo "Umount loop0 if previously mounted"
sudo umount /dev/loop0p1 || true

echo "Mount image on loop0"
sudo partx -a -v "$FILENAME_PREFIX.img"

echo "Create mountpoints and mount image"
mkdir linux/root
mkdir linux/boot
sudo mount /dev/loop0p1 linux/boot

echo "Modify image"
build.sh
sync
sudo umount /dev/loop0p1

echo "Rename image file"
mv "$FILENAME_PREFIX.img" "$FILENAME_PREFIX-navigator.img"

echo "Done!"