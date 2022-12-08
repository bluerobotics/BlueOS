#!/usr/bin/env bash

echo "Configuring BCM28XX board (Raspberry Pi zero, 1, 2, 3).."

CMDLINE_FILE=/boot/cmdline.txt

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
    MODULES_FILE="/etc/modules-load.d/blueos.conf"
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
sudo sed -e 's/console=serial[0-9],[0-9]*\ //' -i $CMDLINE_FILE

# Set cgroup, necessary for docker access to memory information
echo "- Enable cgroup with memory and cpu"
grep -q cgroup $CMDLINE_FILE || (
    # Append cgroups on the first line
    sed -i '1 s/$/ cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory/' $CMDLINE_FILE
)