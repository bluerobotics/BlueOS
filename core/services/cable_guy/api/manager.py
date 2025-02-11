import asyncio
import re
import subprocess
import time
from socket import AddressFamily
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.DHCPServerManager import Dnsmasq as DHCPServerManager
from loguru import logger
from pyroute2 import IW, NDB, IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from api import dns, settings
from networksetup import AbstractNetworkHandler, NetworkHandlerDetector
from typedefs import (
    AddressMode,
    InterfaceAddress,
    InterfaceInfo,
    NetworkInterface,
    NetworkInterfaceMetric,
    NetworkInterfaceMetricApi,
)

__all__ = [
    "AddressMode",
    "EthernetManager",
    "InterfaceAddress",
    "NetworkInterface",
    "NetworkInterfaceMetricApi",
]


class EthernetManager:
    # RTNL interface
    ndb = NDB(log="on")
    # WIFI interface
    iw = IW()
    # IP abstraction interface
    ipr = IPRoute()
    # DNS abstraction
    dns = dns.Dns()
    # Network handler for dhcpd and network manager
    network_handler: AbstractNetworkHandler

    result: List[NetworkInterface] = []

    def __init__(self, default_configs: List[NetworkInterface]) -> None:
        self.network_handler = NetworkHandlerDetector().getHandler()

        self.settings = settings.Settings()

        self._dhcp_servers: List[DHCPServerManager] = []

        # Load settings and do the initial configuration
        if not self.settings.load():
            logger.error(f"Failed to load previous settings. Using default configuration: {default_configs}")
            self.settings.root = {"version": 0, "content": [entry.dict() for entry in default_configs]}

        logger.info("Loading previous settings.")
        for item in self.settings.root["content"]:
            logger.info(f"Loading following configuration: {item}.")
            try:
                self.set_configuration(NetworkInterface(**item))
            except Exception as error:
                logger.error(f"Failed loading saved configuration. {error}")

    def save(self) -> None:
        """Save actual configuration"""
        interfaces = list(self.settings.root["content"])
        self.settings.save(interfaces)

    def set_configuration(self, interface: NetworkInterface, watchdog_call: bool = False) -> None:
        """Modify hardware based in the configuration

        Args:
            interface: NetworkInterface
            watchdog_call: Whether this is a watchdog call
        """
        if not watchdog_call:
            self.network_handler.cleanup_interface_connections(interface.name)
        interfaces = self.get_interfaces()
        valid_names = [interface.name for interface in interfaces]
        if interface.name not in valid_names:
            raise ValueError(f"Invalid interface name ('{interface.name}'). Valid names are: {valid_names}")

        logger.info(f"Setting configuration for interface '{interface.name}'.")
        self.remove_dhcp_server_from_interface(interface.name)

        if interface.addresses:
            # bring interface up
            interface_index = self._get_interface_index(interface.name)
            self.ipr.link("set", index=interface_index, state="up")
        logger.info(f"Configuring addresses for interface '{interface.name}': {interface.addresses}.")
        for address in interface.addresses:
            if address.mode == AddressMode.Unmanaged:
                logger.info(f"Adding static IP '{address.ip}' to interface '{interface.name}'.")
                self.add_static_ip(interface.name, address.ip)
            elif address.mode == AddressMode.Server:
                logger.info(f"Adding DHCP server with gateway '{address.ip}' to interface '{interface.name}'.")
                self.add_dhcp_server_to_interface(interface.name, address.ip)
        # Even if it happened to receive more than one dynamic IP, only one trigger is necessary
        if any(address.mode == AddressMode.Client for address in interface.addresses):
            logger.info(f"Triggering dynamic IP acquisition for interface '{interface.name}'.")
            self.trigger_dynamic_ip_acquisition(interface.name)

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

    def is_valid_interface_name(self, interface_name: str, filter_wifi: bool = False) -> bool:
        """Check if an interface name is valid

        Args:
            interface_name (str): Network interface name
            filter_wifi (boolean, optional): Enable wifi interface filtering

        Returns:
            bool: True if valid, False if not
        """
        blacklist = ["lo", "ham.*", "docker.*", "veth.*"]
        if filter_wifi:
            wifi_interfaces = self._get_wifi_interfaces()
            blacklist += wifi_interfaces

        if not interface_name:
            logger.error("Interface name cannot be blank or null.")
            return False

        for pattern in blacklist:
            if re.match(pattern, interface_name):
                return False

        return True

    def validate_interface_data(self, interface: NetworkInterface, filter_wifi: bool = False) -> bool:
        """Check if interface configuration is valid

        Args:
            interface: NetworkInterface instance
            filter_wifi (boolean, optional): Enable wifi interface filtering

        Returns:
            bool: True if valid, False if not
        """
        return self.is_valid_interface_name(interface.name, filter_wifi)

    @staticmethod
    def _is_server_address_present(interface: NetworkInterface) -> bool:
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
        """Trigger external DHCP servers to possibly acquire a dynamic IP by restarting the interface.

        Args:
            interface_name (str): Interface name
        """
        try:
            self.network_handler.trigger_dynamic_ip_acquisition(interface_name)
            return
        except NotImplementedError as error:
            logger.info(f"Handler does not support triggering dynamic IP acquisition. {error}")
            logger.info(f"Restarting interface {interface_name} to trigger dynamic IP acquisition.")
            self.enable_interface(interface_name, enable=False)
            time.sleep(1)
            self.enable_interface(interface_name, enable=True)
        except Exception as error:
            logger.error(f"Failed to trigger dynamic IP acquisition for interface {interface_name}. {error}")
        finally:
            self.add_static_ip(interface_name, "0.0.0.0", mode=AddressMode.Client)

    def _update_interface_settings(self, interface_name: str, updated_interface: NetworkInterface) -> None:
        """Helper method to update interface settings in a consistent way.

        Args:
            interface_name (str): Name of the interface to update
            updated_interface (NetworkInterface): New interface configuration
        """
        # Filter out the old interface configuration and append the new one
        updated_interfaces = [
            interface for interface in self.settings.root["content"] if interface["name"] != interface_name
        ]
        updated_interfaces.append(updated_interface.dict())
        self.settings.save(updated_interfaces)

    def add_static_ip(self, interface_name: str, ip: str, mode: AddressMode = AddressMode.Unmanaged) -> None:
        """Set ip address for a specific interface

        Args:
            interface_name (str): Interface name
            ip (str): Desired ip address
            mode (AddressMode, optional): Address mode. Defaults to AddressMode.Unmanaged
        """
        logger.info(f"Adding static IP '{ip}' to interface '{interface_name}'.")
        self.network_handler.add_static_ip(interface_name, ip)
        interface_index = self._get_interface_index(interface_name)
        try:
            self.ipr.addr("add", index=interface_index, address=ip, prefixlen=24)
        except Exception as error:
            logger.error(f"Failed to add IP '{ip}' to interface '{interface_name}'. {error}")

        saved_interface = self.get_saved_interface_by_name(interface_name)
        if saved_interface is None:
            # If the interface is not saved, create a new one
            saved_interface = NetworkInterface(
                name=interface_name,
                addresses=[
                    InterfaceAddress(ip=ip, mode=AddressMode.Unmanaged),
                ],
            )
        new_address = InterfaceAddress(ip=ip, mode=mode)
        if new_address not in saved_interface.addresses:
            saved_interface.addresses.append(new_address)
        self._update_interface_settings(interface_name, saved_interface)

    def remove_ip(self, interface_name: str, ip_address: str) -> None:
        """Delete IP address appended on the interface

        Args:
            interface_name (str): Interface name
            ip_address (str): IP address to be deleted
        """
        logger.info(f"Deleting IP {ip_address} from interface {interface_name}.")
        try:
            if (
                self._is_dhcp_server_running_on_interface(interface_name)
                and self._dhcp_server_on_interface(interface_name).ipv4_gateway == ip_address
            ):
                self.remove_dhcp_server_from_interface(interface_name)
            self.network_handler.remove_static_ip(interface_name, ip_address)
        except Exception as error:
            raise RuntimeError(f"Cannot delete IP '{ip_address}' from interface {interface_name}.") from error

        saved_interface = self.get_saved_interface_by_name(interface_name)
        if saved_interface is None:
            logger.error(f"Interface {interface_name} is not managed by Cable Guy. Not deleting IP {ip_address}.")
            return
        saved_interface.addresses = [address for address in saved_interface.addresses if address.ip != ip_address]
        self._update_interface_settings(interface_name, saved_interface)

    def get_interface_by_name(self, name: str) -> NetworkInterface:
        for interface in self.get_ethernet_interfaces():
            if interface.name == name:
                return interface
        raise ValueError(f"No interface with name '{name}' is present.")

    def get_saved_interface_by_name(self, name: str) -> Optional[NetworkInterface]:
        for interface in self.settings.root["content"]:
            if interface["name"] == name:
                return NetworkInterface(**interface)
        return None

    # pylint: disable=too-many-locals
    def get_interfaces(self, filter_wifi: bool = False) -> List[NetworkInterface]:
        """Get interfaces information

        Args:
            filter_wifi (boolean, optional): Enable wifi interface filtering

        Returns:
            List of NetworkInterface instances available
        """
        result = []
        for interface, addresses in psutil.net_if_addrs().items():
            # We don't care about virtual ethernet interfaces
            ## Virtual interfaces are created by programs such as docker
            ## and they are an abstraction of real interfaces, the ones that we want to configure.
            if not self.is_valid_interface_name(interface, filter_wifi):
                continue

            valid_addresses = []
            for address in addresses:
                # We just care about IPV4 addresses
                if not address.family == AddressFamily.AF_INET:
                    continue

                valid_ip = EthernetManager.weak_is_ip_address(address.address)
                ip = address.address if valid_ip else "undefined"

                is_static_ip = self.is_static_ip(ip)

                # Populate our output item
                if (
                    self._is_dhcp_server_running_on_interface(interface)
                    and self._dhcp_server_on_interface(interface).ipv4_gateway == ip
                ):
                    mode = AddressMode.Server
                else:
                    mode = AddressMode.Unmanaged if is_static_ip and valid_ip else AddressMode.Client
                valid_addresses.append(InterfaceAddress(ip=ip, mode=mode))
            info = self.get_interface_info(interface)
            saved_interface = self.get_saved_interface_by_name(interface)
            # Get priority from saved interface or from current interface metrics, defaulting to None if neither exists
            priority = None
            if saved_interface and saved_interface.priority is not None:
                priority = saved_interface.priority
            else:
                interface_metric = self.get_interface_priority(interface)
                if interface_metric:
                    priority = interface_metric.priority

            interface_data = NetworkInterface(name=interface, addresses=valid_addresses, info=info, priority=priority)
            # Check if it's valid and add to the result
            if self.validate_interface_data(interface_data, filter_wifi):
                result += [interface_data]

        return result

    def get_ethernet_interfaces(self) -> List[NetworkInterface]:
        """Get ethernet interfaces information

        Returns:
            List of NetworkInterface instances available
        """
        return self.get_interfaces(filter_wifi=True)

    def get_interface_ndb(self, interface_name: str) -> Any:
        """Get interface NDB information for interface

        Args:
            interface_name (str): Interface name

        Returns:
            pyroute2.ndb.objects.interface.Interface: pyroute2 interface object
        """
        return self.ndb.interfaces.dump().filter(ifname=interface_name)[0]

    @temporary_cache(timeout_seconds=1)
    def get_interfaces_priority(self) -> List[NetworkInterfaceMetric]:
        """Get priority of network interfaces dhcpcd otherwise fetch from ipr.

        Returns:
            List[NetworkInterfaceMetric]: List of interface priorities, lower is higher priority
        """
        return self._get_interfaces_priority_from_ipr()

    def _get_interfaces_priority_from_ipr(self) -> List[NetworkInterfaceMetric]:
        """Get the priority metrics for all network interfaces that are UP and RUNNING.

        Returns:
            List[NetworkInterfaceMetric]: A list of priority metrics for each active interface.
        """

        interfaces = self.ipr.get_links()
        # I hope that you are not here to move this code to IPv6.
        # If that is the case, you'll need to figure out a way to handle
        # priorities between interfaces, between IP categories.
        # GLHF
        routes = self.ipr.get_routes(family=AddressFamily.AF_INET)

        # First find interfaces with default routes
        interfaces_with_default_routes = set()
        for route in routes:
            dst = route.get_attr("RTA_DST")
            oif = route.get_attr("RTA_OIF")
            if dst is None and oif is not None:  # Default route
                interfaces_with_default_routes.add(oif)

        # Generate a dict of index to network name, but only for interfaces that are UP and RUNNING
        # IFF_UP flag is 0x1, IFF_RUNNING is 0x40 in Linux
        name_dict = {
            iface["index"]: iface.get_attr("IFLA_IFNAME")
            for iface in interfaces
            if (iface["flags"] & 0x1) and (iface["flags"] & 0x40) and iface["index"] in interfaces_with_default_routes
        }

        # Get metrics for default routes of active interfaces
        interface_metrics: Dict[int, int] = {}
        for route in routes:
            oif = route.get_attr("RTA_OIF")
            if oif in name_dict and route.get_attr("RTA_DST") is None:  # Only default routes
                metric = route.get_attr("RTA_PRIORITY", 0)
                # Keep the highest metric for each interface
                if oif not in interface_metrics or metric > interface_metrics[oif]:
                    interface_metrics[oif] = metric

        # Create the list of interface metrics
        return [
            NetworkInterfaceMetric(index=index, name=name, priority=interface_metrics.get(index, 0))
            for index, name in name_dict.items()
        ]

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        """Sets network interface priority. This is an abstraction function for different
        implementations.

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics.
                sorted by priority to set, if values are undefined.
        """
        self.network_handler.set_interfaces_priority(interfaces)
        # save to settings
        for interface in interfaces:
            saved_interface = self.get_saved_interface_by_name(interface.name)
            if saved_interface is None:
                saved_interface = NetworkInterface(name=interface.name, addresses=[], priority=interface.priority)
            saved_interface.priority = interface.priority
            self._update_interface_settings(interface.name, saved_interface)

    def get_interface_priority(self, interface_name: str) -> Optional[NetworkInterfaceMetric]:
        """Get the priority metric for a network interface.

        Args:
            interface_name (str): The name of the network interface.

        Returns:
            Optional[NetworkInterfaceMetric]: The priority metric for the interface, or None if no metric found.
        """
        metric: NetworkInterfaceMetric
        for metric in self.get_interfaces_priority():
            if interface_name == metric.name:
                return metric

        return None

    @staticmethod
    def set_interface_priority(name: str, priority: int) -> None:
        """Set interface priority

        Args:
            name (str): Interface name
            priority (int): Priority
        """

        # Change the priority for all routes that are using this interface
        # There is no pretty way of doing it with pyroute2
        result = subprocess.run(
            ["ifmetric", name, str(priority)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to change network priority {name}")

    def get_interface_info(self, interface_name: str) -> InterfaceInfo:
        """Get interface info field

        Args:
            interface_name (str): Interface name

        Returns:
            InterfaceInfo object
        """
        metric = self.get_interface_priority(interface_name)
        priority = metric.priority if metric else 0
        interface = self.get_interface_ndb(interface_name)
        return InterfaceInfo(
            connected=interface.carrier != 0,
            number_of_disconnections=interface.carrier_down_count,
            priority=priority,
        )

    def _is_ip_on_interface(self, interface_name: str, ip_address: str) -> bool:
        interface = self.get_interface_by_name(interface_name)
        return any(True for address in interface.addresses if address.ip == ip_address)

    def _dhcp_server_on_interface(self, interface_name: str) -> DHCPServerManager:
        try:
            return next(dhcp_server for dhcp_server in self._dhcp_servers if dhcp_server.interface == interface_name)
        except StopIteration as error:
            raise ValueError(f"No DHCP server running on interface {interface_name}.") from error

    def _is_dhcp_server_running_on_interface(self, interface_name: str) -> bool:
        try:
            return bool(self._dhcp_server_on_interface(interface_name))
        except Exception:
            return False

    def remove_dhcp_server_from_interface(self, interface_name: str) -> None:
        logger.info(f"Removing DHCP server from interface '{interface_name}'.")
        try:
            self._dhcp_servers.remove(self._dhcp_server_on_interface(interface_name))
        except ValueError:
            # If the interface does not have a DHCP server running on, no need to raise
            pass
        except Exception as error:
            raise RuntimeError("Cannot remove DHCP server from interface.") from error

        saved_interface = self.get_saved_interface_by_name(interface_name)
        if saved_interface is None:
            return
        # Get all non-server addresses
        new_ip_list = [address for address in saved_interface.addresses if address.mode != AddressMode.Server]
        # Find the server address if it exists and convert it to unmanaged
        gateway_addresses = [address for address in saved_interface.addresses if address.mode == AddressMode.Server]
        if gateway_addresses:
            # Convert the server address to unmanaged
            for gateway_address in gateway_addresses:
                new_ip_list.append(InterfaceAddress(ip=gateway_address.ip, mode=AddressMode.Unmanaged))

        saved_interface.addresses = new_ip_list
        self._update_interface_settings(interface_name, saved_interface)

    def add_dhcp_server_to_interface(self, interface_name: str, ipv4_gateway: str) -> None:
        if self._is_dhcp_server_running_on_interface(interface_name):
            self.remove_dhcp_server_from_interface(interface_name)
        if self._is_ip_on_interface(interface_name, ipv4_gateway):
            self.remove_ip(interface_name, ipv4_gateway)
        self.add_static_ip(interface_name, ipv4_gateway, mode=AddressMode.Server)
        logger.info(f"Adding DHCP server with gateway '{ipv4_gateway}' to interface '{interface_name}'.")
        self._dhcp_servers.append(DHCPServerManager(interface_name, ipv4_gateway))

    def stop(self) -> None:
        """Perform steps necessary to properly stop the manager."""
        for dhcp_server in self._dhcp_servers:
            dhcp_server.stop()

    def __del__(self) -> None:
        self.stop()

    def priorities_mismatch(self) -> List[NetworkInterface]:
        """Check if the current interface priorities differ from the saved ones.
        Uses sets for order-independent comparison of NetworkInterfaceMetric objects,
        which compare only name and priority fields.

        Returns:
            bool: True if priorities don't match, False if they do
        """

        mismatched_interfaces = []
        current_priorities = {interface.name: interface.priority for interface in self.get_interfaces_priority()}

        for interface_settings in self.settings.root["content"]:
            interface = NetworkInterface(**interface_settings)
            if interface.priority is None:
                continue
            if interface.name in current_priorities and interface.priority != current_priorities[interface.name]:
                logger.info(
                    f"Priority mismatch for {interface.name}: {interface.priority} != {current_priorities[interface.name]}"
                )
                mismatched_interfaces.append(interface)

        return mismatched_interfaces

    def config_mismatch(self) -> Set[NetworkInterface]:
        """Check if the current interface config differs from the saved ones.

        Returns:
            bool: True if config doesn't match, False if it does
        """

        mismatches: Set[NetworkInterface] = set()
        current = self.get_ethernet_interfaces()
        if "content" not in self.settings.root:
            logger.debug("No saved configuration found")
            logger.debug(f"Current configuration: {self.settings.root}")
            return mismatches

        saved = self.settings.root["content"]
        saved_interfaces = {interface["name"]: NetworkInterface(**interface) for interface in saved}

        for interface in current:
            if interface.name not in saved_interfaces:
                logger.debug(f"Interface {interface.name} not in saved configuration, skipping")
                continue

            for address in saved_interfaces[interface.name].addresses:
                if address.mode == AddressMode.Client:
                    if not any(addr.mode == AddressMode.Client for addr in interface.addresses):
                        logger.info(f"Mismatch detected for {interface.name}: missing dhcp client address")
                        mismatches.add(saved_interfaces[interface.name])
                # Handle Server and Unmanaged modes
                elif address.mode in [AddressMode.Server, AddressMode.Unmanaged]:
                    if address not in interface.addresses:
                        logger.info(
                            f"Mismatch detected for {interface.name}: "
                            f"saved address {address.ip} ({address.mode}) not found in current addresses "
                            f"[{', '.join(f'{addr.ip} ({addr.mode})' for addr in interface.addresses)}]"
                        )
                        mismatches.add(saved_interfaces[interface.name])
        return mismatches

    async def watchdog(self) -> None:
        """
        periodically checks the interfaces states against the saved settings,
        if there is a mismatch, it will apply the saved settings
        """
        while True:
            mismatches = self.config_mismatch()
            if mismatches:
                logger.warning("Interface config mismatch, applying saved settings.")
                logger.debug(f"Mismatches: {mismatches}")
                for interface in mismatches:
                    self.set_configuration(interface, watchdog_call=True)
            priority_mismatch = self.priorities_mismatch()
            if priority_mismatch:
                logger.warning("Interface priorities mismatch, applying saved settings.")
                saved_interfaces = self.settings.root["content"]
                priorities = [
                    NetworkInterfaceMetricApi(name=interface["name"], priority=interface["priority"])
                    for interface in saved_interfaces
                    if "priority" in interface and interface["priority"] is not None
                ]
                self.set_interfaces_priority(priorities)
            await asyncio.sleep(5)
