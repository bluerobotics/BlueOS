#!/usr/bin/env bash

set -e

echo "Configuring a single image for Raspberry Pi 3, 4 and 5.."

VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/BlueOS}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"
if [ -f /boot/firmware/config.txt ]; then
    BOOT_PATH=/boot/firmware
else
    echo "No boot partition at /boot/firmware, is it mounted?" >&2
    echo "Refusing to configure a file the board would never read." >&2
    exit 1
fi
CMDLINE_FILE="$BOOT_PATH/cmdline.txt"
CONFIG_FILE="$BOOT_PATH/config.txt"
alias curl="curl --retry 6 --max-time 15 --retry-all-errors --retry-delay 20 --connect-timeout 60"

echo "- compile spi0 device tree overlay."
DTS_NAME="spi0-led"
curl -fsSL -o /tmp/$DTS_NAME $ROOT/install/overlays/$DTS_NAME.dts
dtc -@ -Hepapr -I dts -O dtb -o "$BOOT_PATH/overlays/$DTS_NAME.dtbo" /tmp/$DTS_NAME

# Every board shares one config.txt, so each board's lines live in its own section. The firmware
# reads only the section of the board it runs on, and a section has to be closed with [all] or the
# settings below it would be limited to that board too.
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
    "^dtoverlay=$" \
    ; do \
    sudo sed -i "/$STRING/d" $CONFIG_FILE
done

# All dtparam lines come first. A dtparam below a dtoverlay changes that overlay, not the board.
# An empty dtoverlay= closes the overlay above it. The dtparam lines below it then go to the board.
# USB gadget mode (dwc2) is left to blueos_startup_update, which also owns the cmdline.txt side of it.
write_board_section() {
    local section="$1"
    shift
    grep -qx "\[$section\]" $CONFIG_FILE || printf '[%s]\n[all]\n' "$section" >> $CONFIG_FILE
    local line_number
    line_number=$(grep -nx "\[$section\]" $CONFIG_FILE | head -n 1 | awk -F ":" '{print $1}')
    local line
    for line in "$@"; do
        sed -i "$line_number r /dev/stdin" $CONFIG_FILE <<< "$line"
        line_number=$((line_number + 1))
    done
}

write_board_section pi3 \
    "dtoverlay=" \
    "dtparam=i2c_arm=on" \
    "dtparam=spi=on" \
    "dtoverlay=spi1-3cs" \
    "dtoverlay=uart1"

write_board_section pi4 \
    "dtoverlay=" \
    "dtparam=i2c_vc=on" \
    "dtparam=i2c_arm_baudrate=1000000" \
    "dtparam=spi=on" \
    "dtoverlay=uart1" \
    "dtoverlay=uart3" \
    "dtoverlay=uart4" \
    "dtoverlay=uart5" \
    "dtoverlay=i2c1" \
    "dtoverlay=i2c4,pins_6_7,baudrate=1000000" \
    "dtoverlay=i2c6,pins_22_23,baudrate=400000" \
    "dtoverlay=spi0-led" \
    "dtoverlay=spi1-3cs" \
    "enable_uart=1" \
    "gpio=11,24,25=op,pu,dh" \
    "gpio=37=op,pd,dl"

write_board_section pi5 \
    "dtoverlay=" \
    "dtparam=i2c_arm=on" \
    "dtparam=spi=on" \
    "dtoverlay=uart0-pi5" \
    "dtoverlay=uart3-pi5" \
    "dtoverlay=uart4-pi5" \
    "dtoverlay=uart2-pi5" \
    "dtoverlay=i2c1" \
    "dtoverlay=i2c3-pi5,baudrate=400000" \
    "dtoverlay=i2c-gpio,i2c_gpio_sda=22,i2c_gpio_scl=23,bus=6,i2c_gpio_delay_us=0" \
    "dtoverlay=spi0-led" \
    "dtoverlay=spi1-3cs" \
    "enable_uart=1" \
    "gpio=11,24,25=op,pu,dh" \
    "gpio=37=op,pd,dl"

if [ -f "/etc/modules" ]; then
    MODULES_FILE="/etc/modules"
else
    MODULES_FILE="/etc/modules-load.d/blueos.conf"
    touch "$MODULES_FILE" || true
fi

echo "- Set up kernel modules."
for STRING in "bcm2835-v4l2" "i2c-bcm2835" "i2c-dev"; do
    sudo sed -i "/$STRING/d" "$MODULES_FILE"
    echo "$STRING" | sudo tee -a "$MODULES_FILE"
done

echo "- Configure serial."
sudo sed -e 's/console=serial[0-9],[0-9]*\ //' -i $CMDLINE_FILE

echo "- Enable cgroup with memory and cpu"
grep -q cgroup $CMDLINE_FILE || (
    sed -i '1 s/$/ cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory/' $CMDLINE_FILE
)

# Boards without an EEPROM (Pi 3) never run this unit's update, so it is safe to set for all
echo "- Force update of VL085 and bootloader on first boot."
SYSTEMD_EEPROM_UPDATE_FILE="/lib/systemd/system/rpi-eeprom-update.service"
sudo sed -i '/^ExecStart=\/usr\/bin\/rpi-eeprom-update -s -a$/c\ExecStart=/bin/bash -c "/usr/bin/rpi-eeprom-update -a -d | (grep \\\"reboot to apply\\\" && echo \\\"Rebooting..\\\" && reboot || exit 0)"' $SYSTEMD_EEPROM_UPDATE_FILE
