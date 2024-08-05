#!/usr/bin/env bash

# Set desired version to be installed
DOCKER_USER="goaschris"  # couldnt work out where to place this var
VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/blueos-docker}
DOCKER_USER=${DOCKER_USER:-$(echo $GITHUB_REPOSITORY | cut -d'/' -f1)}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"

alias curl="curl --retry 6 --max-time 15 --retry-all-errors"

# Additional options
DO_BOARD_CONFIG=1 # default to do the board config
RUNNING_IN_CI=0 # default to not running CI mode/docker-in-docker

usage_help()
{
    cat <<EOF
BlueOS Installer
Usage: install.sh [options]

Options:
    --help                  Show this help
    --skip-board-config     Skip the board-specific configuration.
                            Useful if you are not using Linux ArduPilot.
    --ci-run                Used for building images in CI
EOF
}

get_options()
{
    while [[ $# -gt 0 ]]
    do
        opt="$1"
        case $opt in
            --help)
                usage_help
                exit
                ;;
            --skip-board-config)
                shift
                DO_BOARD_CONFIG=0
                ;;
            --ci-run)
                shift
                RUNNING_IN_CI=1
                ;;
        esac
    done
}
get_options "$@"

# Exit immediately if a command exits with a non-zero status
set -e

# Enable command trace when running over CI
if [ $RUNNING_IN_CI -eq 1 ]
then
    set -x
fi

# Check if the script is running in a supported architecture
SUPPORTED_ARCHITECTURES=(
  "armhf" # Pi, Pi2, Pi3, Pi4
  "armv7" # Pi2, Pi3, Pi4
  "armv7l" # Pi2, Pi3, Pi4 (Raspberry Pi OS Bullseye)
  "aarch64" # Pi3, Pi4
)
ARCHITECTURE="$(uname -m)"
[[ ! "${SUPPORTED_ARCHITECTURES[*]}" =~ $ARCHITECTURE ]] && (
    echo "Invalid architecture: $ARCHITECTURE"
    echo "Supported architectures: ${SUPPORTED_ARCHITECTURES[*]}"
    exit 1
)

# Check if the script is running as root
[[ $EUID != 0 ]] && echo "Script must run as root."  && exit 1

echo "Checking if network and remote are available: $ROOT"
curl -fsSL --silent $ROOT/install/install.sh 1> /dev/null || (
    echo "Remote is not available or install.sh does not exist: ${ROOT}"
    exit 1
)

# Detect CPU and do necessary hardware configuration for each supported hardware
if [ $DO_BOARD_CONFIG -eq 1 ]
then
    echo "Starting hardware configuration."
    curl -fsSL "$ROOT/install/boards/configure_board.sh" | bash
else
    echo "Skipping hardware configuration"
fi

echo "Configure journald."
curl -fsSL "$ROOT/install/configs/journald.conf" -o /etc/systemd/journald.conf

# There are systems where rfkill does not exist, like SBC without wifi/BT
command -v rfkill && (
    echo "Checking for blocked wifi and bluetooth."
    rfkill unblock all
)

# Get the number of free blocks and the block size in bytes, and calculate the value in GB
echo "Checking for available space."

AVAILABLE_SPACE_MB=$(($(stat -f / --format="%a*%S/1024**2")))
NECESSARY_SPACE_MB=1024
(( AVAILABLE_SPACE_MB < NECESSARY_SPACE_MB )) && (
    echo "Not enough free space to install blueos, at least ${NECESSARY_SPACE_MB}MB required"
    exit 1
)

# Check iptables
iptables -v 2>&1 | grep -q "Failed to initialize nft" && (
    echo "iptables command failed. Be sure to fix it before running again."
    echo "Note: If you are running ubuntu or debian, maybe the following command will fix the issue:"
    echo "$ sudo update-alternatives --set iptables /usr/sbin/iptables-legacy"
    exit 1
)

# Check for docker and install it if not found
echo "Checking for docker."
## Docker uses VERSION environment variable to set the docker version,
## We unset this variable for this command to avoid conflicts with blueos version
docker --version || curl -fsSL https://get.docker.com | env -u VERSION sh || (
    echo "Failed to start docker, something may be wrong."
    if [ $RUNNING_IN_CI -ne 1 ]
    then
        exit 1
    fi
    echo "Running in CI is enabled, trying dind."
)

systemctl enable docker

if [ $RUNNING_IN_CI -eq 1 ]
then

    # Download Docker-in-Docker scripts
    # This is used to allow running dockers from within other dockers, as this scripts usually runs in a docker in CI.
    DIND_COMMIT="52379fa76dee07ca038624d639d9e14f4fb719ff"
    curl -fL -o /usr/local/bin/dind "https://raw.githubusercontent.com/moby/moby/${DIND_COMMIT}/hack/dind" && chmod +x /usr/local/bin/dind

    addgroup --system dockremap && \
    adduser --system --ingroup dockremap dockremap && \
    echo 'dockremap:165536:65536' >> /etc/subuid && \
    echo 'dockremap:165536:65536' >> /etc/subgid

    dind dockerd $DOCKER_EXTRA_OPTS &
      while(! docker info > /dev/null 2>&1); do
        echo "==> Waiting for the Docker daemon to come online..."
        sleep 1
      done
    alias docker=dind
fi

sudo usermod -aG docker $USER

# Stop and remove all docker if NO_CLEAN is not defined
test $NO_CLEAN || (
    # Check if there is any docker installed
    [[ $(docker ps -a -q) ]] && (
        echo "Stopping running dockers."
        docker stop $(docker ps -a -q)

        echo "Removing dockers."
        docker rm $(docker ps -a -q)
        docker image prune -af
    ) || true
)

# Start installing necessary files and system configuration
echo "Going to install blueos-docker version ${VERSION}."

echo "Downloading and installing udev rules."
curl -fsSL $ROOT/install/udev/100.autopilot.rules -o /etc/udev/rules.d/100.autopilot.rules

if [ -f /etc/dhcpcd.conf ]
then
    echo "Disabling automatic Link-local configuration in dhcpd.conf."
    # delete line if it already exists
    sed -i '/noipv4ll/d' /etc/dhcpcd.conf
    # add noipv4ll
    sed -i '$ a noipv4ll' /etc/dhcpcd.conf
else
    echo "Not modifying /etc/dhcpcd.conf - file does not exist"
fi

# Do necessary changes if running in a Raspiberry
command -v raspi-config && (
    echo "Running in a Raspiberry."
    if [ $(lsb_release -sc) == "bullseye" ];
    then
        raspi-config nonint get_legacy 1> /dev/null && (
            echo "Enabling legacy camera support."
            raspi-config nonint do_legacy 0
        )
    else
        echo "Not on bullseye - no need to enable legacy camera support"
    fi
)

echo "Downloading bootstrap"
BLUEOS_BOOTSTRAP="$DOCKER_USER/blueos-bootstrap:$VERSION" # Use current version
BLUEOS_CORE="$DOCKER_USER/blueos-core:$VERSION" # We don't have a stable tag yet
BLUEOS_FACTORY="bluerobotics/blueos-core:factory" # used for "factory reset"

docker pull $BLUEOS_BOOTSTRAP
docker pull $BLUEOS_CORE

# Set up default extensions
curl -fsSL $ROOT/install/kraken/set_default_extensions.sh | bash

# Use current release version for factory fallback
docker image tag $BLUEOS_CORE $BLUEOS_FACTORY

# Create blueos-bootstrap container
docker create \
    -t \
    --restart unless-stopped \
    --name blueos-bootstrap \
    --net=host \
    -v $HOME/.config/blueos/bootstrap:/root/.config/bootstrap \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /var/logs/blueos:/var/logs/blueos \
    -e BLUEOS_CONFIG_PATH=$HOME/.config/blueos \
    $BLUEOS_BOOTSTRAP

# add docker entry to rc.local
sed -i "\%^exit 0%idocker start blueos-bootstrap" /etc/rc.local || echo "Failed to add docker start on rc.local, BlueOS will not start on boot!"

# Configure network settings
## This should be after everything, otherwise network problems can happen
echo "Starting network configuration."
curl -fsSL $ROOT/install/network/avahi.sh | bash

# Following https://systemd.io/BUILDING_IMAGES/
echo "Restarting machine-id."
rm -rf /etc/machine-id /var/lib/dbus/machine-id
# The file needs to exist for docker to bind
## if /etc/machine-id does not exist, this is a first boot. During early boot, systemd will write "uninitialized\n"
## to this file and overmount a temporary file which contains the actual machine ID.
## Later (after first-boot-complete.target has been reached), the real machine ID will be written to disk.
## If /etc/machine-id contains the string "uninitialized", a boot is also considered the first boot. The same mechanism as above applies.
echo "uninitialized" > /etc/machine-id
echo "Restarting random-seeds."
rm -rf /var/lib/systemd/random-seed /loader/random-seed

echo "creating dns link"
sudo ln /etc/resolv.conf /etc/resolv.conf.host

echo "Installation finished successfully."
echo "You can access after the reboot:"
echo "- The computer webpage: http://blueos-avahi.local"
echo "- The ssh client: $USER@blueos-avahi.local"
echo "System will reboot in 10 seconds."
sleep 10 && reboot
