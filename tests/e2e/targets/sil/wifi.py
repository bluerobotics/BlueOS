import logging
import re
import shlex

from features.wifi import AccessPoint, WifiAccessPoints, WifiScanner
from targets.target import Target

logger = logging.getLogger(__name__)

# Created at boot by the wifi-lab unit in targets/sil/image/wifi-lab.nix, holding the radios the tests can use
LAB_NETNS = "lab"


class LabNetNamespace:
    def __init__(self, target: Target) -> None:
        self.target = target

    def exec(self, command: str) -> str:
        return self.target.shell(f"sudo ip netns exec {LAB_NETNS} {command}")

    def take_radio(self) -> str:
        # A radio is in use while its link is up
        for line in self.exec("ip -brief link show").splitlines():
            interface, *_, flags = line.split()
            if "UP" not in flags.strip("<>").split(","):
                self.exec(f"ip link set {interface} up")
                return interface
        raise RuntimeError(
            f"all radios in the {LAB_NETNS} namespace are in use, add more by raising labRadios in "
            "targets/sil/image/wifi-lab.nix"
        )

    def release_radio(self, interface: str) -> None:
        self.exec(f"ip addr flush dev {interface}")
        self.exec(f"ip link set {interface} down")


class SilWifiAccessPointsDriver(WifiAccessPoints):
    def __init__(self, target: Target) -> None:
        self.target = target
        self.lab_netns = LabNetNamespace(target)

    def create_access_point(self, ssid: str, channel: int, passphrase: str | None = None) -> AccessPoint:
        interface = self.lab_netns.take_radio()
        logger.info("creating access point %s on %s, channel %s", ssid, interface, channel)
        files = f"/tmp/lab-{interface}"
        subnet = f"10.20.{interface.removeprefix('wlan')}"
        config = [
            f"interface={interface}",
            "driver=nl80211",
            f"ssid={ssid}",
            f"hw_mode={'a' if channel > 14 else 'g'}",
            f"channel={channel}",
            "country_code=US",
            "ieee80211d=1",
        ]
        if passphrase:
            config += ["wpa=2", "wpa_key_mgmt=WPA-PSK", "rsn_pairwise=CCMP", f"wpa_passphrase={passphrase}"]
        hostapd_config = shlex.quote("\n".join(config))
        try:
            self.target.shell(f"sudo mkdir -p {files}")
            self.target.shell(f"printf '%s\\n' {hostapd_config} | sudo tee {files}/hostapd.conf > /dev/null")
            self.lab_netns.exec(f"ip addr add {subnet}.1/24 dev {interface}")
            self.lab_netns.exec(f"hostapd -B -P {files}/hostapd.pid {files}/hostapd.conf")
            self.lab_netns.exec(
                f"dnsmasq --interface={interface} --bind-interfaces --except-interface=lo --port=0 "
                f"--dhcp-range={subnet}.10,{subnet}.50,12h --dhcp-option=3,{subnet}.1 "
                f"--pid-file={files}/dnsmasq.pid --conf-file=/dev/null"
            )
        except RuntimeError:
            self._stop(ssid, interface)
            raise
        return AccessPoint(ssid, lambda: self._stop(ssid, interface))

    def _stop(self, ssid: str, interface: str) -> None:
        logger.info("removing access point %s", ssid)
        files = f"/tmp/lab-{interface}"
        try:
            self.target.shell(f"sudo kill $(cat {files}/*.pid 2> /dev/null) 2> /dev/null; sudo rm -rf {files}")
        finally:
            self.lab_netns.release_radio(interface)


class SilWifiScannerDriver(WifiScanner):
    def __init__(self, target: Target) -> None:
        self.lab_netns = LabNetNamespace(target)

    def scan(self) -> list[str]:
        interface = self.lab_netns.take_radio()
        logger.info("scanning from %s", interface)
        try:
            output = self.lab_netns.exec(f"iw dev {interface} scan flush")
        finally:
            self.lab_netns.release_radio(interface)
        return re.findall(r"^\s*SSID: (.+)$", output, re.MULTILINE)
