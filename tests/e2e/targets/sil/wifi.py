import logging
import shlex

from features.wifi import AccessPoint, WifiAccessPoints, WifiScanner
from targets.sil.vm.ssh import Ssh
from targets.target import Target

logger = logging.getLogger(__name__)

LAB_NETNS = "lab"
LAB_AP_INTERFACES = [f"wlan{index}" for index in range(1, 5)]
LAB_SCANNER_INTERFACE = "wlan5"
LAB_INTERFACES = [*LAB_AP_INTERFACES, LAB_SCANNER_INTERFACE]


def up(ssh: Ssh) -> None:
    # Create a network namespace for the lab
    ssh.run(f"sudo ip netns add {LAB_NETNS} && sudo ip netns exec {LAB_NETNS} ip link set lo up")
    # Move the other radios to the lab namespace
    for interface in LAB_INTERFACES:
        phy = ssh.run(f"sudo iw dev {interface} info | awk '/wiphy/ {{print \"phy\"$2}}'")
        ssh.run(f"sudo iw phy {phy} set netns name {LAB_NETNS}")


class SilWifiAccessPointsDriver(WifiAccessPoints):
    def __init__(self, target: Target) -> None:
        self.target = target
        self.free_interfaces = list(LAB_AP_INTERFACES)

    def create_access_point(self, ssid: str, channel: int, passphrase: str | None = None) -> AccessPoint:
        if not self.free_interfaces:
            raise RuntimeError(f"no free radio left, the lab has {len(LAB_AP_INTERFACES)}")
        interface = self.free_interfaces.pop(0)
        logger.info("creating access point %s on %s, channel %s", ssid, interface, channel)
        subnet = f"10.20.{LAB_AP_INTERFACES.index(interface) + 1}"
        band = "a" if channel > 14 else "g"
        config = (
            f"interface={interface}\ndriver=nl80211\nssid={ssid}\nhw_mode={band}\nchannel={channel}\n"
            "country_code=US\nieee80211d=1\n"
        )
        if passphrase:
            config += f"wpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\nwpa_passphrase={passphrase}\n"
        hostapd_config = f"/tmp/hostapd-{interface}.conf"
        hostapd_pid = f"/tmp/hostapd-{interface}.pid"
        dnsmasq_pid = f"/tmp/dnsmasq-{interface}.pid"
        lab = f"sudo ip netns exec {LAB_NETNS}"
        try:
            self.target.shell(f"printf %s {shlex.quote(config)} | sudo tee {hostapd_config} > /dev/null")
            self.target.shell(f"{lab} ip addr add {subnet}.1/24 dev {interface}")
            self.target.shell(f"{lab} ip link set {interface} up")
            self.target.shell(f"{lab} hostapd -B -P {hostapd_pid} {hostapd_config}")
            self.target.shell(
                f"{lab} dnsmasq --interface={interface} --bind-interfaces --except-interface=lo --port=0 "
                f"--dhcp-range={subnet}.10,{subnet}.50,12h --dhcp-option=3,{subnet}.1 "
                f"--pid-file={dnsmasq_pid} --conf-file=/dev/null"
            )
        except RuntimeError:
            self._stop(interface, hostapd_pid, dnsmasq_pid, hostapd_config)
            raise

        def remove() -> None:
            logger.info("removing access point %s", ssid)
            self._stop(interface, hostapd_pid, dnsmasq_pid, hostapd_config)

        return AccessPoint(ssid, channel, remove)

    def _stop(self, interface: str, hostapd_pid: str, dnsmasq_pid: str, hostapd_config: str) -> None:
        try:
            for pid_file in (dnsmasq_pid, hostapd_pid):
                self.target.shell(f"sudo kill $(cat {pid_file}) 2> /dev/null; sudo rm -f {pid_file}")
            self.target.shell(f"sudo rm -f {hostapd_config}")
            self.target.shell(f"sudo ip netns exec {LAB_NETNS} ip addr flush dev {interface}")
        finally:
            self.free_interfaces.insert(0, interface)


class SilWifiScannerDriver(WifiScanner):
    def __init__(self, target: Target) -> None:
        self.target = target

    def scan(self) -> list[str]:
        logger.info("scanning from %s", LAB_SCANNER_INTERFACE)
        lab = f"sudo ip netns exec {LAB_NETNS}"
        self.target.shell(f"{lab} ip link set {LAB_SCANNER_INTERFACE} up")
        output = self.target.shell(
            f"{lab} iw dev {LAB_SCANNER_INTERFACE} scan flush | sed -n 's/^[[:space:]]*SSID: //p'"
        )
        return [ssid for ssid in output.splitlines() if ssid]
