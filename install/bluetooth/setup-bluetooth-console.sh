#!/usr/bin/env bash
# Set up a Bluetooth serial (RFCOMM/SPP) login console on the BlueOS host.
#
# Pairs over Bluetooth (just works, no PIN) and hands each connection a login
# prompt on the host. Run once on the machine host (not inside docker):
#   sudo bash setup-bluetooth-console.sh
# or:
#   curl -fsSL https://raw.githubusercontent.com/bluerobotics/BlueOS/master/install/bluetooth/setup-bluetooth-console.sh | sudo bash
set -e

[[ $EUID != 0 ]] && echo "Run as root." && exit 1

echo "Installing bluez-tools (bt-agent)"
apt-get install -y --no-install-recommends bluez-tools

echo "Enabling bluetoothd --compat (needed for sdptool SPP)"
BTD=$(command -v bluetoothd || echo /usr/libexec/bluetooth/bluetoothd)
mkdir -p /etc/systemd/system/bluetooth.service.d
printf '[Service]\nExecStart=\nExecStart=%s --compat\n' "$BTD" \
  > /etc/systemd/system/bluetooth.service.d/compat.conf

echo "Installing console launcher"
cat > /usr/bin/blueos-bluetooth-console.sh <<'EOF'
#!/usr/bin/env bash
set -e
ADAPTER=hci0
CHANNEL=1
/usr/sbin/rfkill unblock bluetooth || true
bluetoothctl -- power on || true
bluetoothctl -- system-alias 'BlueOS-BT' || true
bluetoothctl -- pairable on || true
bluetoothctl -- discoverable-timeout 0 || true
bluetoothctl -- discoverable on || true
# persistent just-works pairing agent (auto-accepts, no PIN)
/usr/bin/bt-agent --capability=NoInputNoOutput &
# register Serial Port Profile SDP record (needs bluetoothd --compat)
sdptool add --channel=$CHANNEL SP || true
# setsid: give agetty its own session so it can acquire rfcomm0 as controlling tty
# (without it: "cannot get controlling tty", which breaks the line in weird ways)
# TERM=dumb: over Bluetooth's latency a smart TERM makes bash emit cursor-position
# queries (ESC[6n); the client auto-replies too late and bash runs the reply as a
# command, looping forever. dumb makes readline emit no terminal queries at all.
exec /usr/bin/rfcomm watch "$ADAPTER" "$CHANNEL" /usr/bin/setsid /sbin/agetty --autologin pi --noissue --noclear -L rfcomm0 115200 dumb
EOF
chmod +x /usr/bin/blueos-bluetooth-console.sh

echo "Installing rfcomm shell profile (disable bracketed paste)"
# Bash's bracketed-paste sends a cursor-position query (ESC[6n) each prompt; over
# Bluetooth latency the reply lands too late and bash runs it as a command, looping.
# Disable it only for rfcomm ttys (SSH/console are unaffected).
cat > /etc/profile.d/blueos-bluetooth-console.sh <<'EOF'
case "$(tty 2>/dev/null)" in
  /dev/rfcomm*) bind 'set enable-bracketed-paste off' 2>/dev/null ;;
esac
EOF

echo "Installing systemd service"
cat > /etc/systemd/system/blueos-bluetooth-console.service <<'EOF'
[Unit]
Description=BlueOS Bluetooth serial console
After=bluetooth.service
Requires=bluetooth.service

[Service]
ExecStart=/usr/bin/blueos-bluetooth-console.sh
Restart=on-failure
# bt-agent ignores SIGTERM; don't wait the default 90s on stop/restart
TimeoutStopSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd"
systemctl daemon-reload

# Only restart bluetooth when it is not already in --compat mode. On boards where
# Wi-Fi and Bluetooth share one chip (e.g. Raspberry Pi), restarting the BT stack
# can briefly drop Wi-Fi, so we avoid it on re-runs (the compat drop-in is already live).
if ! pgrep -f 'bluetoothd.*--compat' >/dev/null; then
  echo "Restarting bluetooth to apply --compat (may briefly drop Wi-Fi on combo-chip boards)"
  systemctl restart bluetooth
  sleep 1
fi

echo "Enabling + (re)starting blueos-bluetooth-console"
systemctl enable blueos-bluetooth-console
systemctl restart blueos-bluetooth-console

echo "Done."

# Connect from an Arch Linux client (BlueOS advertises as BlueOS-BT):
#   MAC=$(bluetoothctl devices | grep BlueOS-BT | awk '{print $2}')   # scan/pair first if empty
#   bluetoothctl pair "$MAC" && bluetoothctl trust "$MAC"
#   sudo rfcomm bind 0 "$MAC" 1                                        # persistent /dev/rfcomm0
#   sudo screen /dev/rfcomm0 115200

