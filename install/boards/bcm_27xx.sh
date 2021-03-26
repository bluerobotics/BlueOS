#!/usr/bin/env bash

echo "Configuring BCM27XX board (Raspberry Pi 4).."

# Download, compile, and install spi0 mosi-only device tree overlay for
# neopixel LED on navigator board
echo "- compile spi0 device tree overlay."
DTS_PATH="$REMOTE/$VERSION/install/overlays"
DTS_NAME="spi0-led.dts"
curl -fsSL -o /tmp/$DTS_NAME $DTS_PATH/$DTS_NAME
dtc -@ -Hepapr -I dts -O dtb -o /boot/overlays/spi0-led.dtbo /tmp/$DTS_NAME

# Remove any configuration related to i2c and spi/spi1 and do the necessary changes for navigator
echo "- Enable I2C, SPI and UART."
for STRING in \
    "enable_uart=" \
    "dtoverlay=uart" \
    "dtparam=i2c_arm=" \
    "dtoverlay=i2c" \
    "dtparam=spi=" \
    "dtoverlay=spi"; do \
    sudo sed -i "/$STRING/d" /boot/config.txt
done
for STRING in \
    "enable_uart=1" \
    "dtoverlay=uart1" \
    "dtoverlay=uart2" \
    "dtoverlay=uart3" \
    "dtoverlay=uart4" \
    "dtparam=i2c_arm=on" \
    "dtoverlay=i2c0" \
    "dtoverlay=i2c1" \
    "dtoverlay=i2c4,pins_6_7" \
    "dtoverlay=i2c6,pins_22_23" \
    "dtparam=spi=on" \
    "dtoverlay=spi0-led" \
    "dtoverlay=spi1-3cs"; do \
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
for STRING in "bcm2835-v4l2" "i2c-bcm2835" "i2c-dev"; do
    sudo sed -i "/$STRING/d" "$MODULES_FILE"
    echo "$STRING" | sudo tee -a "$MODULES_FILE"
done

# Remove any console serial configuration
echo "- Configure serial."
sudo sed -e 's/console=serial[0-9],[0-9]*\ //' -i /boot/cmdline.txt