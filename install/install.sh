#!/usr/bin/env bash

# Set desired version to be installed
VERSION="${VERSION:-master}"
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-bluerobotics/blueos-docker}
REMOTE="${REMOTE:-https://raw.githubusercontent.com/${GITHUB_REPOSITORY}}"
ROOT="$REMOTE/$VERSION"

# Additional options
DO_BOARD_CONFIG=1 # default to do the board config

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

echo "Checking if network and remote are available."
curl -fsSL --silent $ROOT/install/install.sh 1> /dev/null || (
    echo "Remote is not available: ${ROOT}"
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

echo "Checking for blocked wifi and bluetooth."
rfkill unblock all

# Get the number of free blocks and the block size in bytes, and calculate the value in GB
echo "Checking for available space."
AVAILABLE_SPACE_GB=$(($(stat -f / --format="%a*%S/1024**3")))
NECESSARY_SPACE_GB=1
(( AVAILABLE_SPACE_GB < NECESSARY_SPACE_GB )) && (
    echo "Not enough free space to install companion, at least ${NECESSARY_SPACE_GB}GB required"
    exit 1
)

# Check for docker and install it if not found
echo "Checking for docker."
## Docker uses VERSION environment variable to set the docker version,
## We unset this variable for this command to avoid conflicts with companion version
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

sudo usermod -aG docker pi

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
echo "Going to install companion-docker version ${VERSION}."

echo "Downloading and installing udev rules."
curl -fsSL $ROOT/install/udev/100.autopilot.rules -o /etc/udev/rules.d/100.autopilot.rules

echo "Disabling automatic Link-local configuration in dhcpd.conf."
# delete line if it already exists
sed -i '/noipv4ll/d' /etc/dhcpcd.conf
# add noipv4ll
sed -i '$ a noipv4ll' /etc/dhcpcd.conf

echo "Downloading bootstrap"
COMPANION_BOOTSTRAP="bluerobotics/companion-bootstrap:master" # We don't have others tags for now
BLUEOS_CORE="bluerobotics/companion-core:$VERSION" # We don't have a stable tag yet

docker pull $COMPANION_BOOTSTRAP
docker pull $BLUEOS_CORE
# Create blueos-bootstrap container
docker create \
    -t \
    --restart unless-stopped \
    --name blueos-bootstrap \
    --net=host \
    -v $HOME/.config/companion/bootstrap:/root/.config/bootstrap \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e COMPANION_CONFIG_PATH=$HOME/.config/companion \
    $COMPANION_BOOTSTRAP

# add docker entry to rc.local
sed -i "\%^exit 0%idocker start blueos-bootstrap" /etc/rc.local || echo "sed failed to add expand_fs entry in /etc/rc.local"

# Configure network settings
## This should be after everything, otherwise network problems can happen
echo "Starting network configuration."
curl -fsSL $ROOT/install/network/avahi.sh | bash

echo "Installation finished successfully."
echo "You can access after the reboot:"
echo "- The computer webpage: http://companion.local"
echo "- The ssh client: pi@companion.local"
echo "System will reboot in 10 seconds."
sleep 10 && reboot