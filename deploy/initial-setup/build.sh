#!/usr/bin/env bash

#For more information: https://www.raspberrypi.com/documentation/computers/linux_kernel.html
cd linux || exit 1

echo "Reset working tree"
git stash --include-untracked

KERNEL=kernel7l
DEFCONFIG=bcm2711_navigator_defconfig
# Get file from outside docker bind
cp $PWD/../../$DEFCONFIG $PWD/arch/arm/configs/
echo "Compiling and installing kernel with: $DEFCONFIG"
make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- $DEFCONFIG
make -j$(nproc) ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- zImage modules dtbs
sudo env PATH=$PATH make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabihf- INSTALL_MOD_PATH=/rootfs modules_install
echo "Copying kernel files"
sudo cp arch/arm/boot/zImage boot/$KERNEL.img
sudo cp arch/arm/boot/dts/*.dtb boot/
sudo mkdir -p boot/overlays
sudo cp arch/arm/boot/dts/overlays/*.dtb* boot/overlays/
sudo cp arch/arm/boot/dts/overlays/README boot/overlays/
sudo touch boot/ssh
