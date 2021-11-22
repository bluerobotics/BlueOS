#!/usr/bin/env bash
cd linux || { echo "unable to cd into 'linux' directory"; exit 1; }

KERNEL=kernel7l
make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- bcm2711_navigator_defconfig
make -j24 ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- zImage modules dtbs
sudo env PATH="$PATH" make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- INSTALL_MOD_PATH=/rootfs modules_install
sudo cp arch/arm/boot/zImage boot/$KERNEL.img
sudo cp arch/arm/boot/dts/*.dtb boot/
sudo mkdir -p boot/overlays
sudo cp arch/arm/boot/dts/overlays/*.dtb* boot/overlays/
sudo cp arch/arm/boot/dts/overlays/README boot/overlays/
# Enable SSH
sudo touch boot/ssh
