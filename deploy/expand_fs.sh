#!/bin/sh

# Borrowed and modified from Raspbian usr/lib/raspi-config/init_resize.sh

# Abort if we are not on a Raspberry Pi
if grep -q 'Hardware.*: BCM2' /proc/cpuinfo; then
    echo "Expanding file system on Raspberry Pi!"
    RPI="1"
else
    echo "This script should only be run on a Raspberry Pi!"
    exit 1
fi

get_variables () {
  ROOT_PART_DEV=$(findmnt / -o source -n)
  #/dev/mmcblk0p2
  ROOT_PART_NAME=$(echo "$ROOT_PART_DEV" | cut -d "/" -f 3)
  #mmcblk0p2
  ROOT_DEV_NAME=$(echo /sys/block/*/"${ROOT_PART_NAME}" | cut -d "/" -f 4)
  #mmcblk0
  ROOT_DEV="/dev/${ROOT_DEV_NAME}"
  #/dev/mmcblk0
  ROOT_PART_NUM=$(cat "/sys/block/${ROOT_DEV_NAME}/${ROOT_PART_NAME}/partition")
  #2

  BOOT_PART_DEV=$(findmnt /boot -o source -n)
  BOOT_PART_NAME=$(echo "$BOOT_PART_DEV" | cut -d "/" -f 3)
  BOOT_DEV_NAME=$(echo /sys/block/*/"${BOOT_PART_NAME}" | cut -d "/" -f 4)
  BOOT_PART_NUM=$(cat "/sys/block/${BOOT_DEV_NAME}/${BOOT_PART_NAME}/partition")

  OLD_DISKID=$(fdisk -l "$ROOT_DEV" | sed -n 's/Disk identifier: 0x\([^ ]*\)/\1/p')

  check_noobs

  ROOT_DEV_SIZE=$(cat "/sys/block/${ROOT_DEV_NAME}/size")
  TARGET_END=$((ROOT_DEV_SIZE - 1))

  PARTITION_TABLE=$(parted -m "$ROOT_DEV" unit s print | tr -d 's')

  LAST_PART_NUM=$(echo "$PARTITION_TABLE" | tail -n 1 | cut -d ":" -f 1)

  ROOT_PART_LINE=$(echo "$PARTITION_TABLE" | grep -e "^${ROOT_PART_NUM}:")
  ROOT_PART_START=$(echo "$ROOT_PART_LINE" | cut -d ":" -f 2)
  ROOT_PART_END=$(echo "$ROOT_PART_LINE" | cut -d ":" -f 3)
  echo Root part end: $ROOT_PART_END
  echo target end: $TARGET_END
}

get_variables

if ! parted -m "$ROOT_DEV" u s resizepart "$ROOT_PART_NUM" "$TARGET_END"; then
	FAIL_REASON="Root partition resize failed"
	return 1
fi

resize2fs -p $ROOT_PART_DEV

sed -i '\%/usr/bin/expand_fs.sh%d' /etc/rc.local
