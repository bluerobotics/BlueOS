import asyncio
import re
from socket import AddressFamily
from typing import Any, Dict, List, Tuple

import psutil
from api import settings
from pyroute2 import IW, NDB, IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg


class EthernetManager:
    # RTNL interface
    ndb = NDB(log="on")
    # WIFI interface
    iw = IW()
    # IP abstraction interface
    ipr = IPRoute()

    result: List[Dict[str, Any]] = []

    def __init__(self) -> None:
        self.settings = settings.Settings()

        # Load settings and do the initial configuration
        if not self.settings.load():
            print("Failed to load previous settings.")
            return

        print("Previous settings loaded:")
        for item in self.settings.root["content"]:
            print(f"Configuration with: {item}")
            if not self.set_configuration(item):
                print("Failed.")

    def save(self) -> None:
        """Save actual configuration"""
        try:
            self.get_interfaces()
        except Exception as exception:
            print(f"Failed to fetch actual configuration, going to use the previous info: {exception}")

        if not self.result:
            print("Configuration is empty, aborting.")
            return

        for item in self.result:
            item.pop("info")
        self.settings.save(self.result)

    def set_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Modify hardware based in the configuration

        Args:
            configuration (dict): Configuration struct
                {
                    'name': 'interface_name',
                    'configuration': {
                        'ip': 'ip_address',
                        'mode': 'mode' // [unmanaged, client, server],
                    }
                }

        Returns:
            bool: Configuration was accepted
        """
        interfaces = self.get_interfaces()
        valid_names = [interface["name"] for interface in interfaces]

        name = configuration["name"]
        ip = configuration["configuration"]["ip"]
        mode = configuration["configuration"]["mode"]

        if name not in valid_names:
            return False

        if mode == "client":
            self.set_dynamic_ip(name)
            return True
        if mode == "unmanaged":
            self.set_static_ip(name, ip)
            return True

        return False

    def _get_wifi_interfaces(self) -> List[str]:
        """Get wifi interface list

        Returns:
            list: List with the name of the wifi interfaces
        """
        interfaces = self.iw.list_dev()
        result = []
        for interface in interfaces:
            for flag, value in interface["attrs"]:
                # Extract interface name from IFNAME flag
                if flag == "NL80211_ATTR_IFNAME":
                    result += [value]
        return result

    def is_valid_interface(self, interface: str) -> bool:
        """Check if an interface is valid

        Args:
            interface (str): Network interface

        Returns:
            bool: True if valid, False if not
        """
        blacklist = ["lo", "ham.*", "docker.*"]
        blacklist += self._get_wifi_interfaces()

        if not interface:
            return False

        for pattern in blacklist:
            if re.match(pattern, interface):
                return False

        return True

    def validate_interface_data(self, data: Dict[str, Any]) -> bool:
        """Check if interface configuration is valid

        Args:
            data (dict): Interface dict structure

        Returns:
            bool: True if valid, False if not
        """
        name = data["name"]
        return self.is_valid_interface(name)

    @staticmethod
    def weak_is_ip_address(ip: str) -> bool:
        """Check if ip address is valid

        Args:
            ip (str): ip address

        Returns:
            bool: True if valid, False if not
        """
        return re.match(r"\d+.\d+.\d+.\d+", ip) is not None

    def is_static_ip(self, ip: str) -> bool:
        """Check if ip address is static or dynamic
            For more information: https://code.woboq.org/qt5/include/linux/if_addr.h.html
                https://www.systutorials.com/docs/linux/man/8-ip-address/

        Args:
            ip (str): ip address

        Returns:
            bool: true if static false if not
        """
        for address in list(self.ipr.get_addr()):

            def get_item(items: List[Tuple[str, Any]], name: str) -> Any:
                return [value for key, value in items if key == name][0]

            if get_item(address["attrs"], "IFA_ADDRESS") != ip:
                continue

            flags = get_item(address["attrs"], "IFA_FLAGS")
            result = "IFA_F_PERMANENT" in ifaddrmsg.flags2names(flags)
            return result
        return False

    def _get_interface_index(self, interface_name: str) -> int:
        """Get interface index for internal usage

        Args:
            interface_name (str): Interface name

        Returns:
            int: Interface index
        """
        interface_index = int(self.ipr.link_lookup(ifname=interface_name)[0])
        return interface_index

    def flush_interface(self, interface_name: str) -> None:
        """Flush all ip addresses in a specific interface

        Args:
            interface_name (str): Interface name
        """
        interface_index = self._get_interface_index(interface_name)
        self.ipr.flush_addr(index=interface_index)

    def enable_interface(self, interface_name: str, enable: bool = True) -> None:
        """Enable interface

        Args:
            interface_name (str): Interface name
            enable (bool, optional): Set interface status. Defaults to True
        """
        interface_index = self._get_interface_index(interface_name)
        interface_state = "up" if enable else "down"
        self.ipr.link("set", index=interface_index, state=interface_state)

    async def _trigger_dhcp_service(self, interface_name: str) -> None:
        """Internal async trigger for dhcp service

        Args:
            interface_name (str): Interface name
        """
        self.enable_interface(interface_name, False)
        await asyncio.sleep(1)
        self.enable_interface(interface_name, True)

    def trigger_dhcp_service(self, interface_name: str) -> None:
        """Trigger DHCP service via async

        Args:
            interface_name (str): Interface name
        """
        asyncio.run(self._trigger_dhcp_service(interface_name))

    def set_ip(self, interface_name: str, ip: str) -> None:
        """Set ip address for a specific interface

        Args:
            interface_name (str): Interface name
            ip (str): Desired ip address
        """
        interface_index = self._get_interface_index(interface_name)
        self.ipr.addr("add", index=interface_index, address=ip, prefixlen=24)

    def set_dynamic_ip(self, interface_name: str) -> None:
        """Set interface to use dynamic ip address

        Args:
            interface_name (str): Interface name
        """
        # Remove all address
        self.flush_interface(interface_name)
        # Trigger DHCP service to add a new dynamic ip address
        self.trigger_dhcp_service(interface_name)

    def set_static_ip(self, interface_name: str, ip: str) -> None:
        """Set interface to use static ip address

        Args:
            interface_name (str): Interface name
            ip (str): ip address
        """
        # Remove all address
        self.flush_interface(interface_name)
        # Set new ip address
        self.set_ip(interface_name, ip)

    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get interfaces information

        Returns:
            dict: Interface information that uses the following struct:
            [
                {
                    'name': 'interface_name',
                    'configuration': {
                        'ip': 'ip_address',
                        'mode': 'mode' // [unmanaged, client, server],
                    },
                    'info': {
                        'connected': True,
                        'number_of_disconnections': 4,
                    }
                },
                ...
            ]
        """
        result = []
        for interface, addresses in psutil.net_if_addrs().items():
            for address in addresses:
                # We don't care about ipv6
                if address.family == AddressFamily.AF_INET6:
                    continue

                # If there is no ip address the mac address will be provided (⊙＿⊙')
                valid_ip = EthernetManager.weak_is_ip_address(address.address)
                ip = address.address if valid_ip else "undefined"

                is_static_ip = self.is_static_ip(ip)

                # Populate our output item
                mode = "unmanaged" if is_static_ip and valid_ip else "client"
                info = self.get_interface_info(interface)
                data = {
                    "name": interface,
                    "configuration": {"ip": ip, "mode": mode},
                    "info": info,
                }

                # Check if it's valid and add to the result
                if self.validate_interface_data(data):
                    result += [data]
                    break

        self.result = result
        return result

    def get_interface_ndb(self, interface_name: str) -> Any:
        """Get interface NDB information for interface

        Args:
            interface_name (str): Interface name

        Returns:
            pyroute2.ndb.objects.interface.Interface: pyroute2 interface object
        """
        return self.ndb.interfaces.dump().filter(ifname=interface_name)[0]

    def get_interface_info(self, interface_name: str) -> Dict[str, Any]:
        """Get interface info field

        Args:
            interface_name (str): Interface name

        Returns:
            dict: Info field of `get_interfaces`
        """
        interface = self.get_interface_ndb(interface_name)
        return {
            "connected": interface.carrier != 0,
            "number_of_disconnections": interface.carrier_down_count,
        }


ethernetManager = EthernetManager()

if __name__ == "__main__":
    from pprint import pprint

    pprint(ethernetManager.get_interfaces())
