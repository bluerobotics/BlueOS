import pathlib
import re
import time
from enum import Enum
from socket import AddressFamily
from typing import Any, List, Optional, Tuple

import psutil
from commonwealth.utils.DHCPServerManager import Dnsmasq
from loguru import logger
from pydantic import BaseModel
from pyroute2 import IW, NDB, IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from api import settings


class AddressMode(str, Enum):
    Client = "client"
    Server = "server"
    Unmanaged = "unmanaged"


class InterfaceAddress(BaseModel):
    ip: str
    mode: AddressMode


class InterfaceInfo(BaseModel):
    connected: bool
    number_of_disconnections: int


class EthernetInterface(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo]


class EthernetManager:
    # RTNL interface
    ndb = NDB(log="on")
    # WIFI interface
    iw = IW()
    # IP abstraction interface
    ipr = IPRoute()

    result: List[EthernetInterface] = []

    def __init__(self, default_config: EthernetInterface, dhcp_gateway: str) -> None:
        self.settings = settings.Settings()

        self._config_path = pathlib.Path(__file__).parent.absolute().joinpath("settings", "dnsmasq.conf")
        self._server = Dnsmasq(self._config_path)
        self._dhcp_server_gateway = dhcp_gateway

        # Load settings and do the initial configuration
        if not self.settings.load():
            logger.error(f"Failed to load previous settings. Using default configuration: {default_config}")
            try:
                self.set_configuration(default_config)
            except Exception as error:
                logger.error(f"Failed loading default configuration. {error}")
            return

        logger.info("Loading previous settings.")
        for item in self.settings.root["content"]:
            logger.info(f"Loading following configuration: {item}.")
            try:
                self.set_configuration(EthernetInterface(**item))
            except Exception as error:
                logger.error(f"Failed loading saved configuration. {error}")

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

    def set_configuration(self, interface: EthernetInterface) -> None:
        """Modify hardware based in the configuration

        Args:
            interface: EthernetInterface
        """
        interfaces = self.get_interfaces()
        logger.debug(f"Found following ethernet interfaces: {interfaces}.")
        valid_names = [interface.name for interface in interfaces]

        if interface.name not in valid_names:
            raise ValueError(f"Invalid interface name ('{interface.name}'). Valid names are: {valid_names}")

        self.flush_interface(interface.name)

        for address in interface.addresses:
            self.add_ip(interface.name, address.mode, address.ip)

        if not self._is_server_address_present(interface) and self._server.is_running():
            self._server.stop()

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
    def _is_server_address_present(interface: EthernetInterface) -> bool:
        return any(address.mode == AddressMode.Server for address in interface.addresses)

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

    def trigger_dynamic_ip_acquisition(self, interface_name: str) -> None:
        """Trigger external DHCP servers to possibly aquire a dynamic IP by restarting the interface.

        Args:
            interface_name (str): Interface name
        """
        logger.info(f"Restaring interface {interface_name} to trigger dynamic IP acquisition.")
        self.enable_interface(interface_name, False)
        time.sleep(1)
        self.enable_interface(interface_name, True)

    def set_ip(self, interface_name: str, ip: str) -> None:
        """Set ip address for a specific interface

        Args:
            interface_name (str): Interface name
            ip (str): Desired ip address
        """
        interface_index = self._get_interface_index(interface_name)
        self.ipr.addr("add", index=interface_index, address=ip, prefixlen=24)
        logger.info(f"Setting interface {interface_name} to IP '{ip}'.")

    def set_static_ip(self, interface_name: str, ip: str) -> None:
        """Set interface to use static ip address

        Args:
            interface_name (str): Interface name
            ip (str): ip address
        """
        # Set new ip address
        self.set_ip(interface_name, ip)

    def add_ip(self, interface_name: str, mode: AddressMode, ip_address: Optional[str] = None) -> None:
        """Add IP address to a given interface

        Args:
            interface_name (str): Interface name
            ip_address (str): IP address to be added
        """
        parsed_ip = self._dhcp_server_gateway if not ip_address and mode == AddressMode.Server else ip_address
        logger.info(f"Adding IP '{parsed_ip}' on interface '{interface_name}' in {mode} mode.")
        try:
            interface = self.get_interface_by_name(interface_name)

            if parsed_ip is None or parsed_ip == "" and mode in [AddressMode.Unmanaged, AddressMode.Server]:
                raise ValueError("No IP address was specified. Cannot add static IP.")

            # Remove old IP address, if it already exists, and use the new one
            for address in interface.addresses:
                if address.ip == parsed_ip:
                    self.remove_ip(interface_name, parsed_ip)

            if mode == AddressMode.Client:
                self.trigger_dynamic_ip_acquisition(interface_name)
                return
            if mode == AddressMode.Server:
                self.set_static_ip(interface_name, parsed_ip)
                if not self._server.is_running():
                    self._server.start()
                return
            if mode == AddressMode.Unmanaged:
                self.set_static_ip(interface_name, parsed_ip)
        except Exception as error:
            error_msg = f"Cannot add IP '{parsed_ip}' to interface {interface_name}. {error}"
            logger.error(error_msg)
            raise ValueError(error_msg) from error

    def remove_ip(self, interface_name: str, ip_address: str) -> None:
        """Delete IP address appended on the interface

        Args:
            interface_name (str): Interface name
            ip_address (str): IP address to be deleted
        """
        logger.info(f"Deleting IP {ip_address} from interface {interface_name}.")
        try:
            interface = self.get_interface_by_name(interface_name)
            if self._is_server_address_present(interface) and self._server.is_running():
                self._server.stop()
            interface_index = self._get_interface_index(interface_name)
            self.ipr.addr("del", index=interface_index, address=ip_address, prefixlen=24)
        except Exception as error:
            error_msg = f"Cannot delete IP '{ip_address}' from interface {interface_name}. {error}"
            logger.error(error_msg)
            raise ValueError(error_msg) from error

    def get_interface_by_name(self, name: str) -> EthernetInterface:
        for interface in self.get_interfaces():
            if interface.name == name:
                return interface
        raise ValueError(f"No interface with name '{name}' is present.")

    def get_interfaces(self) -> List[EthernetInterface]:
        """Get interfaces information

        Returns:
            List of EthernetInterface instances available
        """
        result = []
        for interface, addresses in psutil.net_if_addrs().items():
            # We don't care about virtual ethernet interfaces
            ## Virtual interfaces are created by programs such as docker
            ## and they are an abstraction of real interfaces, the ones that we want to configure.
            if str(interface).startswith("veth"):
                continue

            valid_addresses = []
            for address in addresses:
                # We just care about IPV4 addresses
                if not address.family == AddressFamily.AF_INET:
                    continue

                valid_ip = EthernetManager.weak_is_ip_address(address.address)
                ip = address.address if valid_ip else "undefined"

                is_static_ip = self.is_static_ip(ip)
                is_gateway_ip = ip == self._dhcp_server_gateway

                # Populate our output item
                if self._server.is_running() and is_gateway_ip:
                    mode = AddressMode.Server
                else:
                    mode = AddressMode.Unmanaged if is_static_ip and valid_ip else AddressMode.Client
                info = self.get_interface_info(interface)
                valid_addresses.append(InterfaceAddress(ip=ip, mode=mode))

            interface_data = EthernetInterface(name=interface, addresses=valid_addresses, info=info)
            # Check if it's valid and add to the result
            if self.validate_interface_data(interface_data):
                result += [interface_data]

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
