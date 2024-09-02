#!/usr/bin/env bash

# Detect and configure hardware for each supported plataform
VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/blueos-docker}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"
CONFIGURE_BOARD_PATH="$ROOT/install/boards"
alias curl="curl --retry 6 --max-time 15 --retry-all-errors"

function board_not_detected {
    echo "Hardware not identified in $1, please report back the following line:"
    echo "---"
    echo "$(echo $2 | gzip | base64 -w0)" # Decode with `echo $CONTENT | base64 -d | gunzip`
    echo "---"
}

echo "Detecting board type"
# device-tree/model is not standard but is the only way to detect raspberry pi hardware reliable
#  From Raspberry Pi official website about Raspberry Pi 4 cpuinfo:
#  Why does cpuinfo report I have a BCM2835?
#     The upstream Linux kernel developers had decided that all models of Raspberry Pi return bcm2835 as the SoC name.
#     Unfortunately it means that cat /proc/cpuinfo is inaccurate for the Raspberry Pi 2, Raspberry Pi 3 and Raspberry Pi 4,
#     which use the bcm2836/bcm2837, bcm2837 and bcm2711 respectively.
#     You can use cat /proc/device-tree/model to get an accurate description of the SoC on your Raspberry Pi model.
if [ -f "/proc/device-tree/model" ]; then
    CPU_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    if [[ $CPU_MODEL =~ Raspberry\ Pi\ [0-3] ]]; then
        echo "Detected BCM28XX via device tree"
        curl -fsSL $CONFIGURE_BOARD_PATH/bcm_28xx.sh | bash
    elif [[ $CPU_MODEL =~ (Raspberry\ Pi\ [4])|(Raspberry\ Pi\ Compute\ Module\ 4.*) ]]; then
        echo "Detected BCM27XX via device tree"
        curl -fsSL $CONFIGURE_BOARD_PATH/bcm_27xx.sh | bash
    elif [[ $CPU_MODEL =~ Raspberry\ Pi\ 5 ]]; then
        echo "Detected Raspberry Pi 5 via device tree"
        curl -fsSL $CONFIGURE_BOARD_PATH/bcm_2712.sh | bash
    else
        board_not_detected "/proc/device-tree/model" "$CPU_MODEL"
    fi

# If the previous file does not exist, we are going to try the old method and do our best
# BTW: This method is not recommended at all
# Ref: https://github.com/raspberrypi/documentation/blob/2cf115ef449929a6be865a4418418f85af975e37/documentation/asciidoc/computers/raspberry-pi/revision-codes.adoc
elif [ -f "/proc/cpuinfo" ]; then
    CPU_INFO="$(cat /proc/cpuinfo)"
    if [[ $CPU_INFO =~ BCM27[0-9]{2} ]]; then
        echo "Detected BCM27XX via cpuinfo"
        curl -fsSL $CONFIGURE_BOARD_PATH/bcm_27xx.sh | bash
    elif [[ $CPU_INFO =~ BCM28[0-9]{2} ]]; then
        echo "Detected BCM28XX via cpuinfo"
        curl -fsSL $CONFIGURE_BOARD_PATH/bcm_28xx.sh | bash
    else
        board_not_detected "/proc/cpuinfo" "$CPU_INFO"
    fi

else
    echo "Impossible to detect hardware, aborting."
    exit 255
fi
