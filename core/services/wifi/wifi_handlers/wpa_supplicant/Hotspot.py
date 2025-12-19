import asyncio
import hashlib
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import time
from enum import Enum
from ipaddress import IPv4Address
from typing import Any, Callable, List, Optional

import psutil
from commonwealth.utils.DHCPServerManager import Dnsmasq as DHCPServerManager
from commonwealth.utils.general import HostOs, device_id, get_host_os
from loguru import logger
from pyroute2 import IW, IPRoute
from typedefs import WifiCredentials


class HostapdFrequency(str, Enum):
    """Valid hostapd frequency modes."""

    HW_2_4 = "g"  # Hostapd id for 2.4 GHz mode
    HW_5_0 = "a"  # Hostapd id for 5.0 GHz mode

    @staticmethod
    def mode_from_channel_frequency(frequency: int) -> "HostapdFrequency":
        return HostapdFrequency.HW_2_4 if int(frequency / 100) == 24 else HostapdFrequency.HW_5_0


class HotspotManager:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        base_interface: str,
        ipv4_gateway: IPv4Address,
        ap_interface_name: str = "uap0",
        ap_ssid: Optional[str] = None,
        ap_passphrase: Optional[str] = None,
    ) -> None:
        self.iw = IW()
        self.ipr = IPRoute()

        self._ap_interface_name = ap_interface_name
        self.supports_hotspot = self.check_hotspot_support()
        try:
            dev_id = device_id()
        except Exception:
            dev_id = "000000"
        hashed_id = hashlib.md5(dev_id.encode()).hexdigest()[:6]
        self._ap_ssid = ap_ssid or f"BlueOS ({hashed_id})"

        self._ap_passphrase = ap_passphrase or "blueosap"

        self._subprocess: Optional[Any] = None

        if base_interface not in psutil.net_if_stats():
            raise ValueError(f"Base interface '{base_interface}' not found.")
        self._base_interface = base_interface

        self._ipv4_gateway = ipv4_gateway

        self._include_interface_on_dhcpcd()

        self._dhcp_server: Optional[DHCPServerManager] = None

        binary_path = shutil.which(self.binary_name())
        if binary_path is None:
            raise ValueError("Hostapd binary not found on system's PATH.")

        self._binary = pathlib.Path(binary_path)
        assert self.is_binary_working()

    @staticmethod
    def binary_name() -> str:
        return "hostapd"

    def binary(self) -> pathlib.Path:
        return self._binary

    def check_hotspot_support(self) -> bool:
        # Support for Bookworm should arrive with NetworkManager support
        return bool(get_host_os() == HostOs.Bullseye)

    def set_credentials(self, credentials: WifiCredentials) -> None:
        logger.debug(f"Changing hotspot ssid to '{credentials.ssid}' and passphrase to '{credentials.password}'.")
        self._ap_ssid = credentials.ssid
        self._ap_passphrase = credentials.password

    @property
    def credentials(self) -> WifiCredentials:
        return WifiCredentials(ssid=self._ap_ssid, password=self._ap_passphrase)

    def is_binary_working(self) -> bool:
        try:
            subprocess.check_output([self.binary(), "-h"])
            return True
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                return True
            logger.error(f"Invalid binary: {error}")
            return False

    def base_interface_channel_frequency(self) -> int:
        wireless_interfaces = self.iw.get_interfaces_dict()
        if self._base_interface not in wireless_interfaces:
            raise RuntimeError("Could not find base interface.")
        last_channel = -1
        time_last_channel_change = time.time()
        time_start_searching = time.time()
        while True:
            current_channel = int(wireless_interfaces[self._base_interface][3])
            if current_channel != last_channel:
                time_last_channel_change = time.time()
                last_channel = current_channel
            seconds_in_same_channel = time.time() - time_last_channel_change
            seconds_searching = time.time() - time_start_searching
            if seconds_in_same_channel > 2:
                return current_channel
            if seconds_searching > 15:
                raise RuntimeError("Could not find base interface channel. Timeout exceeded.")

    def desired_channel_frequency(self) -> int:
        return self.base_interface_channel_frequency()

    def _create_virtual_interface(self) -> None:
        logger.debug("Deleting virtual access point interface (if exists).")
        wireless_interfaces = self.iw.get_interfaces_dict()
        if self._ap_interface_name in wireless_interfaces:
            interface_index = int(self.ipr.link_lookup(ifname=self._ap_interface_name)[0])
            self.iw.del_interface(interface_index)
        self._reach_condition_or_timeout(
            lambda self: self._ap_interface_name not in self.iw.get_interfaces_dict(),
            "Could not delete virtual interface. Timeout exceeded.",
        )

        logger.debug("Creating virtual access point interface.")
        # pylint: disable=consider-using-with
        subprocess.Popen(
            shlex.split(f"iw dev {self._base_interface} interface add {self._ap_interface_name} type __ap")
        )
        # Following 2 lines are an alternative I could not get to work since its docs are not very clear
        # base_interface_index = int(self.ipr.link_lookup(ifname=self._base_interface)[0])
        # self.iw.add_interface(ifname=self._ap_interface_name, iftype="ap_vlan", dev=base_interface_index)
        self._reach_condition_or_timeout(
            lambda self: self._ap_interface_name in psutil.net_if_stats(),
            "Could not create virtual interface. Timeout exceeded.",
        )

        logger.debug("Starting virtual access point interface.")
        # pylint: disable=consider-using-with
        subprocess.Popen(shlex.split(f"ifconfig {self._ap_interface_name} up"))
        # Following 2 lines are an alternative I could not get to work since its docs are not very clear
        # virtual_interface_index = int(self.ipr.link_lookup(ifname=self._ap_interface_name)[0])
        # self.ipr.link("set", index=virtual_interface_index, state="up")
        self._reach_condition_or_timeout(
            lambda self: self._ap_interface_name in psutil.net_if_stats() and psutil.net_if_stats()[self._ap_interface_name][0],  # fmt: skip
            "Could not start virtual interface. Timeout exceeded.",
        )

    def command_list(self) -> List[str]:
        return shlex.split(f"{self.binary()} {self.config_path()}")

    async def start(self) -> None:
        logger.info("Starting hotspot.")
        if not self.supports_hotspot:
            raise RuntimeError("Hotspot not supported on this device.")
        try:
            self._create_temp_config_file()
            self._create_virtual_interface()
            # pylint: disable=consider-using-with
            if not self.is_running():
                self._subprocess = subprocess.Popen(self.command_list(), shell=False, encoding="utf-8", errors="ignore")
                await asyncio.sleep(3)
                if not self.is_running():
                    exit_code = self._subprocess.returncode
                    stdout, _ = self._subprocess.communicate()
                    raise RuntimeError(f"Failed to initialize Hostapd ({exit_code}). Output: {stdout}")
            if not self._dhcp_server:
                self._dhcp_server = DHCPServerManager(self._ap_interface_name, self._ipv4_gateway)
                return
            await self._dhcp_server.restart()
        except Exception as error:
            raise RuntimeError(f"Unable to start hotspot. {error}") from error

    def stop(self) -> None:
        logger.info("Stopping hotspot.")
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
            if not self._dhcp_server:
                logger.warning("Cannot stop DHCP server for hotspot, as was already not running.")
                return
            self._dhcp_server.stop()
        else:
            logger.info("Tried to stop hostpot, but it was already not running.")

    async def restart(self) -> None:
        self.stop()
        await self.start()

    def is_running(self) -> bool:
        if not self.supports_hotspot:
            return False
        return self._subprocess is not None and self._subprocess.poll() is None

    @staticmethod
    def config_path() -> pathlib.Path:
        config_dir = pathlib.Path(tempfile.tempdir or "/")
        return config_dir.joinpath("hostapd.conf")

    def hostapd_config(self) -> str:
        desired_channel_frequency = self.desired_channel_frequency()
        desired_channel_number = HotspotManager.channel_number(desired_channel_frequency)

        return (
            "# WiFi interface to be used (in this case a virtual one)\n"
            f"interface={self._ap_interface_name}\n"
            "# Channel (frequency) of the access point\n"
            f"channel={desired_channel_number}\n"
            "# SSID broadcasted by the access point\n"
            f'ssid2="{self._ap_ssid}"\n'
            "# Passphrase for the access point\n"
            f"wpa_passphrase={self._ap_passphrase}\n"
            "# Operation mode. Uses 'g' for 2.4GHz bands and 'a' for 5GHz.\n"
            f"hw_mode={HostapdFrequency.mode_from_channel_frequency(desired_channel_frequency).value}\n"
            "# Accept all MAC addresses\n"
            "macaddr_acl=0\n"
            "# Use WPA authentication\n"
            "auth_algs=1\n"
            "# Require clients to know the network name\n"
            "ignore_broadcast_ssid=0\n"
            "# Use WPA2\n"
            "wpa=2\n"
            "# Use a pre-shared key\n"
            "wpa_key_mgmt=WPA-PSK\n"
            "wpa_pairwise=TKIP\n"
            "rsn_pairwise=CCMP\n"
        )

    def _create_temp_config_file(self) -> None:
        logger.info(f"Saving temporary hostapd config file on {self.config_path()}")
        with open(self.config_path(), "w", encoding="utf-8") as f:
            f.write(self.hostapd_config())

    def _include_interface_on_dhcpcd(self) -> None:
        if not self.supports_hotspot:
            return
        with open("/etc/dhcpcd.conf", "r", encoding="utf-8") as f:
            original_lines = f.readlines()

            start_line = -1
            end_line = -1
            for i, line in enumerate(original_lines):
                if "blueos-start" in line:
                    start_line = i
                if "blueos-end" in line:
                    end_line = i
            lines_to_remove: List[int] = []
            if start_line != -1 and end_line != -1:
                lines_to_remove = list(range(start_line, end_line + 1))

            new_lines = []
            for i, line in enumerate(original_lines):
                if i not in lines_to_remove:
                    new_lines.append(line)

            if not str(new_lines[-1]).endswith("\n"):
                new_lines.append("\n")

            if str(new_lines[-1]) != "\n":
                new_lines.append("\n")
            new_lines.append("#blueos-start\n")
            new_lines.append(f"interface {self._ap_interface_name}\n")
            new_lines.append(f"    static ip_address={self._ipv4_gateway}/24\n")
            new_lines.append("    nohook wpa_supplicant\n")
            new_lines.append("END\n")
            new_lines.append("#blueos-end\n")

        with open("/etc/dhcpcd.conf", "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _reach_condition_or_timeout(self, condition: Callable[["HotspotManager"], bool], timeout_message: str) -> None:
        time_start = time.time()
        while True:
            if condition(self):
                time.sleep(0.3)
                break
            if time.time() - time_start > 5:
                raise RuntimeError(timeout_message)
            time.sleep(0.1)

    @staticmethod
    def channel_number(frequency: int) -> int:
        return {
            2412: 1,
            2417: 2,
            2422: 3,
            2427: 4,
            2432: 5,
            2437: 6,
            2442: 7,
            2447: 8,
            2452: 9,
            2457: 10,
            2462: 11,
            2467: 12,
            2472: 13,
            2484: 14,
            5035: 7,
            5040: 8,
            5045: 9,
            5055: 11,
            5060: 12,
            5080: 16,
            5160: 32,
            5170: 34,
            5180: 36,
            5190: 38,
            5200: 40,
            5210: 42,
            5220: 44,
            5230: 46,
            5240: 48,
            5250: 50,
            5260: 52,
            5270: 54,
            5280: 56,
            5290: 58,
            5300: 60,
            5310: 62,
            5320: 64,
            5340: 68,
            5480: 96,
            5500: 100,
            5510: 102,
            5520: 104,
            5530: 106,
            5540: 108,
            5550: 110,
            5560: 112,
            5570: 114,
            5580: 116,
            5590: 118,
            5600: 120,
            5610: 122,
            5620: 124,
            5630: 126,
            5640: 128,
            5660: 132,
            5670: 134,
            5680: 136,
            5690: 138,
            5700: 140,
            5710: 142,
            5720: 144,
            5745: 149,
            5755: 151,
            5765: 153,
            5775: 155,
            5785: 157,
            5795: 159,
            5805: 161,
            5815: 163,
            5825: 165,
            5835: 167,
            5845: 169,
            5855: 171,
            5865: 173,
            5875: 175,
            5885: 177,
            5910: 182,
            5915: 183,
            5920: 184,
            5935: 187,
            5940: 188,
            5945: 189,
            5960: 192,
            5980: 196,
        }[frequency]
