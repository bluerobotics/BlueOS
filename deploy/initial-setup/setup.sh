#!/usr/bin/env bash
FILE=raspios_lite_armhf-2021-11-08/2021-10-30-raspios-bullseye-armhf-lite.zip
FILENAME=$(basename $FILE)
wget -nc https://downloads.raspberrypi.org/raspios_lite_armhf/images/$FILE
unzip -n "$FILENAME"

git clone --depth 1  --branch rpi-4.19.y https://github.com/Williangalvani/linux

sudo partx -a -v ./*.img
# create mountpoints and mount image
mkdir linux/root
mkdir linux/boot

# Get first partition (boot) of loop device
# shellcheck disable=SC2012
PARTITION=$(ls /dev/loop*  | tail -n 2 | head -n 1)
sudo mount "$PARTITION" linux/boot

echo "Starting build!"
build.sh
ls linux/boot
echo "Build done!"
sync
sudo umount "$PARTITION" --detach-loop
sync
echo "done!"
