#!/usr/bin/env bash

# Running in a BCM27/28, do necessary (Raspberry)
echo "Configuring BCM27/28 board.."

# Remove any configuration related to i2c and spi/spi1 and do the necessary changes for navigator
echo "- Enable I2C, SPI and UART."
for STRING in "dtparam=i2c_arm=" "dtparam=spi=" "dtoverlay=spi1" "dtoverlay=uart1"; do
    sudo sed -i "/$STRING/d" /boot/config.txt
done
for STRING in "dtparam=i2c_arm=on" "dtparam=spi=on" "dtoverlay=spi1-3cs" "dtoverlay=uart1"; do
    echo "$STRING" | sudo tee -a /boot/config.txt
done

# Check for valid modules file to load kernel modules
if [ -f "/etc/modules" ]; then
    MODULES_FILE="/etc/modules"
else
    MODULES_FILE="/etc/modules-load.d/companion.conf"
    touch "$MODULES_FILE" || true # Create if it does not exist
fi

echo "- Set up kernel modules."
# Remove any configuration or commented part related to the i2c drive
for STRING in "bcm2835-v4l2" "i2c-bcm2708" "i2c-dev"; do
    sudo sed -i "/$STRING/d" "$MODULES_FILE"
    echo "$STRING" | sudo tee -a "$MODULES_FILE"
done

# Remove any console serial configuration
echo "- Configure serial."
sudo sed -e 's/console=serial[0-9],[0-9]*\ //' -i /boot/cmdline.txt