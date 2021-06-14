import asyncio
import re
from enum import Enum
from socket import AddressFamily
from typing import Any, List, Optional, Tuple

import psutil
from loguru import logger
from pydantic import BaseModel
from pyroute2 import IW, NDB, IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from api import settings


class InterfaceMode(str, Enum):
    Client = "client"
    Server = "server"
    Unmanaged = "unmanaged"


class InterfaceConfiguration(BaseModel):
    ip: str
    mode: InterfaceMode


class InterfaceInfo(BaseModel):
    connected: bool
    number_of_disconnections: int


class EthernetInterface(BaseModel):
    name: str
    configuration: InterfaceConfiguration
    info: Optional[InterfaceInfo]


class EthernetManager:
    # RTNL interface
    ndb = NDB(log="on")
    # WIFI interface
    iw = IW()
    # IP abstraction interface
    ipr = IPRoute()

    result: List[EthernetInterface] = []

    def __init__(self, default_config: EthernetInterface) -> None:
        self.settings = settings.Settings()

        # Load settings and do the initial configuration
        if not self.settings.load():
            logger.error(f"Failed to load previous settings. Using default configuration: {default_config}")
            self.set_configuration(default_config)
            return

        logger.info("Previous settings loaded:")
        for item in self.settings.root["content"]:
            logger.info(f"Configuration with: {item}")
            if not self.set_configuration(EthernetInterface(**item)):
                logger.error("Failed.")

    def save(self) -> None:
        """Save actual configuration"""
        try:
            self.get_interfaces()
        except Exception as exception:
            logger.error(f"Failed to fetch actual configuration, going to use the previous info: {exception}")

        if not self.result:
            logger.error("Configuration is empty, aborting.")
            return

        result = [interface.dict(exclude={"info"}) for interface in self.result]
        self.settings.save(result)

    def set_configuration(self, interface: EthernetInterface) -> bool:
        """Modify hardware based in the configuration

        Args:
            interface: EthernetInterface

        Returns:
            bool: Configuration was accepted
        """
        interfaces = self.get_interfaces()
        logger.debug(f"Found following ethernet interfaces: {interfaces}.")
        valid_names = [interface.name for interface in interfaces]

        name = interface.name
        ip = interface.configuration.ip
        mode = interface.configuration.mode

        if name not in valid_names:
            logger.error(f"Invalid interface name ('{name}'). Valid names are: {valid_names}")
            return False

        if mode == InterfaceMode.Client:
            self.set_dynamic_ip(name)
            logger.info(f"Interface '{name}' configured with dynamic IP.")
            return True
        if mode == InterfaceMode.Unmanaged:
            self.set_static_ip(name, ip)
            logger.info(f"Interface '{name}' configured with static IP.")
            return True

        logger.error(f"Could not configure interface '{name}'.")
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

    def is_valid_interface_name(self, interface_name: str) -> bool:
        """Check if an interface name is valid

        Args:
            interface_name (str): Network interface name

        Returns:
            bool: True if valid, False if not
        """
        blacklist = ["lo", "ham.*", "docker.*"]
        wifi_interfaces = self._get_wifi_interfaces()
        blacklist += wifi_interfaces

        if not interface_name:
            logger.error("Interface name cannot be blank or null.")
            return False

        for pattern in blacklist:
            if re.match(pattern, interface_name):
                return False

        return True

    def validate_interface_data(self, interface: EthernetInterface) -> bool:
        """Check if interface configuration is valid

        Args:
            interface: EthernetInterface instance

        Returns:
            bool: True if valid, False if not
        """
        return self.is_valid_interface_name(interface.name)

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
        logger.info(f"Flushing IP addresses from interface {interface_name}.")

    def enable_interface(self, interface_name: str, enable: bool = True) -> None:
        """Enable interface

        Args:
            interface_name (str): Interface name
            enable (bool, optional): Set interface status. Defaults to True
        """
        interface_index = self._get_interface_index(interface_name)
        interface_state = "up" if enable else "down"
        self.ipr.link("set", index=interface_index, state=interface_state)
        logger.info(f"Setting interface {interface_name} to '{interface_state}' state.")

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
        logger.info(f"Setting interface {interface_name} to IP '{ip}'.")

    def set_dynamic_ip(self, interface_name: str) -> None:
        """Set interface to use dynamic ip address

        Args:
            interface_name (str): Interface name
        """
        # Remove all address
        self.flush_interface(interface_name)
        # Trigger DHCP service to add a new dynamic ip address
        self.trigger_dhcp_service(interface_name)
        logger.info(f"Getting dynamic IP to interface {interface_name}.")

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

    def get_interfaces(self) -> List[EthernetInterface]:
        """Get interfaces information

        Returns:
            List of EthernetInterface instances available
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
                mode = InterfaceMode.Unmanaged if is_static_ip and valid_ip else InterfaceMode.Client
                info = self.get_interface_info(interface)
                data = EthernetInterface(
                    name=interface, configuration=InterfaceConfiguration(ip=ip, mode=mode), info=info
                )

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

    def get_interface_info(self, interface_name: str) -> InterfaceInfo:
        """Get interface info field

        Args:
            interface_name (str): Interface name

        Returns:
            InterfaceInfo object
        """
        interface = self.get_interface_ndb(interface_name)
        return InterfaceInfo(connected=interface.carrier != 0, number_of_disconnections=interface.carrier_down_count)
