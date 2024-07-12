#!/usr/bin/env bash

echo "Configuring BCM27XX board (Raspberry Pi 4).."

VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/blueos-docker}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"
CMDLINE_FILE=/boot/cmdline.txt
CONFIG_FILE=/boot/config.txt
alias curl="curl --retry 6 --max-time 15 --retry-all-errors"

# Download, compile, and install spi0 mosi-only device tree overlay for
# neopixel LED on navigator board
echo "- compile spi0 device tree overlay."
DTS_PATH="$ROOT/install/overlays"
DTS_NAME="spi0-led"
curl -fsSL -o /tmp/$DTS_NAME $DTS_PATH/$DTS_NAME.dts
dtc -@ -Hepapr -I dts -O dtb -o /boot/overlays/$DTS_NAME.dtbo /tmp/$DTS_NAME

# Remove any configuration related to i2c and spi/spi1 and do the necessary changes for navigator
echo "- Enable I2C, SPI and UART."
for STRING in \
    "enable_uart=" \
    "dtoverlay=uart" \
    "dtparam=i2c" \
    "dtoverlay=i2c" \
    "dtparam=spi=" \
    "dtoverlay=spi" \
    "gpio=" \
    "dwc2" \
    ; do \
    sudo sed -i "/$STRING/d" $CONFIG_FILE
done

# add [pi4] if it is not there
if ! grep -q "\[pi4\]" $CONFIG_FILE; then
    echo "[pi4]" >> $CONFIG_FILE
fi
# find the line number of the [pi4] tag

line_number=$(grep -n "\[pi4\]" $CONFIG_FILE | awk -F ":" '{print $1}')
echo "Line number of [pi4] tag: $line_number"


for STRING in \
    "enable_uart=1" \
    "dtoverlay=uart1" \
    "dtoverlay=uart3" \
    "dtoverlay=uart4" \
    "dtoverlay=uart5" \
    "dtparam=i2c_vc=on" \
    "dtoverlay=i2c1" \
    "dtparam=i2c_arm_baudrate=1000000" \
    "dtoverlay=i2c4,pins_6_7,baudrate=1000000" \
    "dtoverlay=i2c6,pins_22_23,baudrate=400000" \
    "dtparam=spi=on" \
    "dtoverlay=spi0-led" \
    "dtoverlay=spi1-3cs" \
    "gpio=11,24,25=op,pu,dh" \
    "gpio=37=op,pd,dl" \
    "dtoverlay=dwc2,dr_mode=otg" \
    ; do \
    sed -i "$line_number r /dev/stdin" $CONFIG_FILE <<< "$STRING"
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

echo "- Enable USB OTG as ethernet adapter"
grep -q dwc2 $CMDLINE_FILE || (
    # Append cgroups on the first line
    sed -i '1 s/$/ modules-load=dwc2,g_ether/' $CMDLINE_FILE
)

# Force update of bootloader and VL085 firmware on the first boot
echo "- Force update of VL085 and bootloader on first boot."
SYSTEMD_EEPROM_UPDATE_FILE="/lib/systemd/system/rpi-eeprom-update.service"
sudo sed -i '/^ExecStart=\/usr\/bin\/rpi-eeprom-update -s -a$/c\ExecStart=/bin/bash -c "/usr/bin/rpi-eeprom-update -a -d | (grep \\\"reboot to apply\\\" && echo \\\"Rebooting..\\\" && reboot || exit 0)"' $SYSTEMD_EEPROM_UPDATE_FILE