#!/usr/bin/env bash

# Trixie ignores custom.toml and provisions the first boot through cloud-init. Remove cloud-init, and provision
# the user, ssh and hostname here instead.
set -e

grep -q VERSION_CODENAME=trixie /etc/os-release || exit 0

# Only the installed ones, apt refuses to purge a package the base image does not have
dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' cloud-init rpi-cloud-init-mods 2>/dev/null |
    awk '/^ii/ {print $2}' | DEBIAN_FRONTEND=noninteractive xargs -r apt-get purge -y
# Same password hash as install/boards/config.toml, it has to stay literal
# shellcheck disable=SC2016
/usr/lib/userconf-pi/userconf pi '$5$jN49NV5TpvPOd.dA$cNLchFFnGqbYgyyHpIs5jZwCgAFbTb6QhaxiN8UdjO/'
systemctl enable ssh
echo blueos > /etc/hostname
sed -i 's/^127.0.1.1.*/127.0.1.1\tblueos/' /etc/hosts

# Trixie no longer grants the first user passwordless sudo, and the host commands BlueOS runs through ssh
# (boot patches, firmware info, network setup) have no terminal to ask for a password
echo "pi ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/010_pi-nopasswd
chmod 440 /etc/sudoers.d/010_pi-nopasswd

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
unmanaged-devices=interface:eth0;interface:usb0
CONF
