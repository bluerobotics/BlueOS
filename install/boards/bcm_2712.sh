#!/usr/bin/env bash

set -e

echo "Configuring BCM2712 board (Raspberry Pi 5).."

VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/BlueOS}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"
CMDLINE_FILE=/boot/firmware/cmdline.txt
CONFIG_FILE=/boot/firmware/config.txt
alias curl="curl --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60"

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

# add [pi5] if it is not there
if ! grep -q "\[pi5\]" $CONFIG_FILE; then
    echo "[pi5]" >> $CONFIG_FILE
fi
# find the line number of the [pi5] tag

line_number=$(grep -n "\[pi5\]" $CONFIG_FILE | awk -F ":" '{print $1}')
echo "Line number of [pi5] tag: $line_number"


for STRING in \
    "enable_uart=1" \
    "dtoverlay=uart0-pi5" \
    "dtoverlay=uart3-pi5" \
    "dtoverlay=uart4-pi5" \
    "dtoverlay=uart2-pi5" \
    "dtparam=i2c_arm=on" \
    "dtoverlay=i2c1" \
    "dtoverlay=i2c3-pi5,baudrate=400000" \
    "dtoverlay=i2c3-pi5.baudrate=400000" \
    "dtoverlay=i2c-gpio,i2c_gpio_sda=22,i2c_gpio_scl=23,bus=6,i2c_gpio_delay_us=0" \
    "dtparam=spi=on" \
    "dtoverlay=spi0-led" \
    "dtoverlay=spi1-3cs" \
    "gpio=11,24,25=op,pu,dh" \
    "gpio=37=op,pd,dl" \
    "dtoverlay=dwc2,dr_mode=peripheral" \
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
