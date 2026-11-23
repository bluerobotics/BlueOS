#!/usr/bin/env bash

# Trixie ignores custom.toml and provisions the first boot through cloud-init. Remove cloud-init, and provision
# the user, ssh and hostname here instead.
set -e

grep -q VERSION_CODENAME=trixie /etc/os-release || exit 0

# What a simulated purge would remove that is not cloud-init. A simulated purge prints "Purg <package> [...]", and a
# simulated remove "Remv", so accept both.
unexpected_removals() {
    awk '/^(Purg|Remv) / {print $2}' | grep -vxE 'cloud-init|rpi-cloud-init-mods' || true
}

# Only the installed ones, apt refuses to purge a package the base image does not have
CLOUD_INIT_PACKAGES=$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' cloud-init rpi-cloud-init-mods 2>/dev/null |
    awk '/^ii/ {print $2}')
if [ -n "$CLOUD_INIT_PACKAGES" ]; then
    # Purging also removes whatever depends on the packages, so look at what would go before it does
    # shellcheck disable=SC2086
    SIMULATION=$(apt-get -s purge $CLOUD_INIT_PACKAGES)
    UNEXPECTED=$(unexpected_removals <<< "$SIMULATION")
    if [ -n "$UNEXPECTED" ]; then
        echo "Purging cloud-init would also remove: ${UNEXPECTED//$'\n'/ }, refusing." >&2
        exit 1
    fi
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive apt-get purge -y $CLOUD_INIT_PACKAGES
fi

# Same password hash as install/boards/config.toml, it has to stay literal
# shellcheck disable=SC2016
/usr/lib/userconf-pi/userconf pi '$5$jN49NV5TpvPOd.dA$cNLchFFnGqbYgyyHpIs5jZwCgAFbTb6QhaxiN8UdjO/'
[ "$(id -u pi)" = 1000 ] || { echo "The pi user is not the first user (uid 1000)." >&2; exit 1; }
systemctl enable ssh
echo blueos > /etc/hostname
# Without a line for the hostname every sudo prints "unable to resolve host"
if grep -q '^127.0.1.1' /etc/hosts; then
    sed -i 's/^127.0.1.1.*/127.0.1.1\tblueos/' /etc/hosts
else
    printf '127.0.1.1\tblueos\n' >> /etc/hosts
fi

# Trixie no longer grants the first user passwordless sudo, and the host commands BlueOS runs through ssh
# (boot patches, firmware info, network setup) have no terminal to ask for a password
printf 'pi ALL=(ALL) NOPASSWD: ALL\n' > /tmp/010_pi-nopasswd
visudo -cf /tmp/010_pi-nopasswd
install -m 440 /tmp/010_pi-nopasswd /etc/sudoers.d/010_pi-nopasswd
rm /tmp/010_pi-nopasswd

# NetworkManager rewrites /etc/resolv.conf as empty on its first boot, which breaks the host DNS (ntp and image pulls)
# until blueos_startup_update gets to set dns=none. Keep in sync with configure_network_manager().
cat > /etc/NetworkManager/NetworkManager.conf << 'CONF'
[main]
plugins=ifupdown,keyfile
dns=none

[ifupdown]
managed=false

[device]
wifi.scan-rand-mac-address=no

[keyfile]
unmanaged-devices=interface-name:eth0;interface-name:usb0
CONF

# Trixie's systemd-sysctl only reads /etc/sysctl.d. Keep in sync with ensure_ipv6_disabled().
cat > /etc/sysctl.d/99-blueos.conf << 'SYSCTL'
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
net.ipv6.conf.lo.disable_ipv6=1
SYSCTL

# rpi-swap disables zram on its own for hosts like the Pi3, and Bookworm's dphys-swapfile is gone. Without swap the
# Pi3 (905 MB) thrashes on the SD card a minute after boot until the watchdog reboots it.
mkdir -p /etc/rpi/swap.conf.d
printf '[Main]\nMechanism=zram\n' > /etc/rpi/swap.conf.d/blueos.conf
