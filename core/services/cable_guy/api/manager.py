import re
import subprocess
import time
from socket import AddressFamily
from typing import Any, Dict, List, Optional, Tuple

import psutil
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.DHCPServerManager import Dnsmasq as DHCPServerManager
from loguru import logger
from pyroute2 import IW, NDB, IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from api import dns, settings

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

    # https://man.archlinux.org/man/dhcpcd.conf.5#metric
    default_dhcpdc_metric = 1000

    result: List[NetworkInterface] = []

    def __init__(self, default_configs: List[NetworkInterface]) -> None:
        self.dhcpcd_conf_path = "/etc/dhcpcd.conf"
        self.dhcpcd_conf_start_string = "#blueos-interface-priority-start"
        self.dhcpcd_conf_end_string = "#blueos-interface-priority-end"

        self.settings = settings.Settings()

        self._dhcp_servers: List[DHCPServerManager] = []

        # Load settings and do the initial configuration
        if not self.settings.load():
            logger.error(f"Failed to load previous settings. Using default configuration: {default_configs}")
            try:
                for config in default_configs:
                    self.set_configuration(config)
            except Exception as error:
                logger.error(f"Failed loading default configuration. {error}")
            return

        logger.info("Loading previous settings.")
        for item in self.settings.root["content"]:
            logger.info(f"Loading following configuration: {item}.")
            try:
                self.set_configuration(NetworkInterface(**item))
            except Exception as error:
                logger.error(f"Failed loading saved configuration. {error}")

    def save(self) -> None:
        """Save actual configuration"""
        try:
            self.get_ethernet_interfaces()
        except Exception as exception:
            logger.error(f"Failed to fetch actual configuration, going to use the previous info: {exception}")

        if not self.result:
            logger.error("Configuration is empty, aborting.")
            return

        result = [interface.dict(exclude={"info"}) for interface in self.result]
        self.settings.save(result)

    def set_configuration(self, interface: NetworkInterface) -> None:
        """Modify hardware based in the configuration

        Args:
            interface: NetworkInterface
        """
        interfaces = self.get_ethernet_interfaces()
        logger.debug(f"Found following ethernet interfaces: {interfaces}.")
        valid_names = [interface.name for interface in interfaces]

        if interface.name not in valid_names:
            raise ValueError(f"Invalid interface name ('{interface.name}'). Valid names are: {valid_names}")

        # Reset the interface by removing all IPs and DHCP servers associated with it
        self.flush_interface(interface.name)
        self.remove_dhcp_server_from_interface(interface.name)

        # Even if it happened to receive more than one dynamic IP, only one trigger is necessary
        if any(address.mode == AddressMode.Client for address in interface.addresses):
            self.trigger_dynamic_ip_acquisition(interface.name)

        for address in interface.addresses:
            if address.mode == AddressMode.Unmanaged:
                self.add_static_ip(interface.name, address.ip)
            elif address.mode == AddressMode.Server:
                self.add_dhcp_server_to_interface(interface.name, address.ip)

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
        logger.info(f"Restarting interface {interface_name} to trigger dynamic IP acquisition.")
        self.enable_interface(interface_name, False)
        time.sleep(1)
        self.enable_interface(interface_name, True)

    def add_static_ip(self, interface_name: str, ip: str) -> None:
        """Set ip address for a specific interface

        Args:
            interface_name (str): Interface name
            ip (str): Desired ip address
        """
        logger.info(f"Adding static IP '{ip}' to interface '{interface_name}'.")
        interface_index = self._get_interface_index(interface_name)
        self.ipr.addr("add", index=interface_index, address=ip, prefixlen=24)

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
            interface_index = self._get_interface_index(interface_name)
            self.ipr.addr("del", index=interface_index, address=ip_address, prefixlen=24)
        except Exception as error:
            raise RuntimeError(f"Cannot delete IP '{ip_address}' from interface {interface_name}.") from error

    def get_interface_by_name(self, name: str) -> NetworkInterface:
        for interface in self.get_ethernet_interfaces():
            if interface.name == name:
                return interface
        raise ValueError(f"No interface with name '{name}' is present.")

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
            interface_data = NetworkInterface(name=interface, addresses=valid_addresses, info=info)
            # Check if it's valid and add to the result
            if self.validate_interface_data(interface_data, filter_wifi):
                result += [interface_data]

        self.result = result
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
        result = self._get_interface_priority_from_dhcpcd()
        if result:
            return result

        return self._get_interfaces_priority_from_ipr()

    def _get_interfaces_priority_from_ipr(self) -> List[NetworkInterfaceMetric]:
        """Get the priority metrics for all network interfaces.

        Returns:
            List[NetworkInterfaceMetric]: A list of priority metrics for each interface.
        """

        interfaces = self.ipr.get_links()
        # I hope that you are not here to move this code to IPv6.
        # If that is the case, you'll need to figure out a way to handle
        # priorities between interfaces, between IP categories.
        # GLHF
        routes = self.ipr.get_routes(family=AddressFamily.AF_INET)

        # Generate a dict of index to network name.
        # And a second list between the network index and metric,
        # keep in mind that a single interface can have multiple routes
        name_dict = {iface["index"]: iface.get_attr("IFLA_IFNAME") for iface in interfaces}
        metric_index_list = [
            {"metric": route.get_attr("RTA_PRIORITY", 0), "index": route.get_attr("RTA_OIF")} for route in routes
        ]

        # Keep the highest metric per interface in a dict of index to metric
        metric_dict: Dict[int, int] = {}
        for d in metric_index_list:
            if d["index"] in metric_dict:
                metric_dict[d["index"]] = max(metric_dict[d["index"]], d["metric"])
            else:
                metric_dict[d["index"]] = d["metric"]

        # Highest priority wins for ipr but not for dhcpcd, so we sort and reverse the list
        # Where we change the priorities between highest and low to convert that
        original_list = sorted(
            [
                NetworkInterfaceMetric(index=index, name=name, priority=metric_dict.get(index) or 0)
                for index, name in name_dict.items()
            ],
            key=lambda x: x.priority,
            reverse=True,
        )

        return [
            NetworkInterfaceMetric(index=item.index, name=item.name, priority=original_list[-(i + 1)].priority)
            for i, item in enumerate(original_list)
        ]

    def _get_service_dhcpcd_content(self) -> List[str]:
        """Returns a list of lines from the dhcpcd configuration file that belong to
        this service.
        Any exceptions are caught and logged, and an empty list is returned.

        List[str]: Lines that will be used by this service
        """
        try:
            with open(self.dhcpcd_conf_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

                start, end = None, None
                for i, line in enumerate(lines):
                    # Get always the first occurrence of 'start' and last of 'end'
                    if self.dhcpcd_conf_start_string in line and start is None:
                        start = i
                    if self.dhcpcd_conf_end_string in line:
                        end = i

                # Remove everything that is not from us
                if start is not None and end is not None:
                    del lines[0 : start + 1]
                    del lines[end:-1]

                # Clean all lines and remove empty ones
                lines = [line.strip() for line in lines]
                lines = [line for line in lines if line]
                return lines
        except Exception as exception:
            logger.warning(f"Failed to read {self.dhcpcd_conf_path}, error: {exception}")
            return []

    def _get_interface_priority_from_dhcpcd(self) -> List[NetworkInterfaceMetric]:
        """Parses dhcpcd config file to get network interface priorities.
        Goes through the dhcpcd config file line by line looking for "interface"
        and "metric" lines. Extracts the interface name and metric value. The
        metric is used as the priority, with lower being better.

        List[NetworkInterfaceMetric]: A list of priority metrics for each interface.
        """
        lines = self._get_service_dhcpcd_content()
        result = []
        current_interface = None
        current_metric = None
        for line in lines:
            if line.startswith("interface"):
                if current_interface is not None and current_metric is not None:  # type: ignore[unreachable]
                    # Metric is inverted compared to priority, lowest metric wins
                    result.append(NetworkInterfaceMetric(index=0, name=current_interface, priority=current_metric))  # type: ignore[unreachable]

                current_interface = line.split()[1]
                current_metric = None

            elif line.startswith("metric") and current_interface is not None:
                try:
                    current_metric = int(line.split()[1])
                except Exception as exception:
                    logger.error(
                        f"Failed to parse {current_interface} metric, error: {exception}, line: {line}, using default metric"
                    )
                    current_metric = EthernetManager.default_dhcpdc_metric

        # Add the last entry to the result_list
        if current_interface is not None and current_metric is not None:
            result.append(NetworkInterfaceMetric(index=0, name=current_interface, priority=current_metric))

        return result

    def _remove_dhcpcd_configuration(self) -> None:
        """Removes the network priority configuration added by this service from
        dhcpcd.conf file.
        """
        lines = []
        with open(self.dhcpcd_conf_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            start, end = None, None
            for i, line in enumerate(lines):
                # Get always the first occurrence of 'start' and last of 'end'
                if self.dhcpcd_conf_start_string in line and start is None:
                    start = i
                if self.dhcpcd_conf_end_string in line:
                    end = i

            # Remove our part
            if start is not None and end is not None:
                logger.info(f"Deleting rage: {start} : {end + 1}")
                del lines[start : end + 1]
            else:
                logger.info(f"There is no network priority configuration in {self.dhcpcd_conf_path}")
                return

        if not lines:
            logger.warning(f"{self.dhcpcd_conf_path} appears to be empty.")
            return

        with open("/etc/dhcpcd.conf", "w", encoding="utf-8") as f:
            f.writelines(lines)

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        """Sets network interface priority. This is an abstraction function for different
        implementations.

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics.
                sorted by priority to set, if values are undefined.
        """
        self._set_interfaces_priority_to_dhcpcd(interfaces)

    def _set_interfaces_priority_to_dhcpcd(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        """Sets network interface priority..

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics.
        """

        # Note: With DHCPCD, lower priority wins!
        self._remove_dhcpcd_configuration()

        # Update interfaces priority if possible
        if not interfaces:
            logger.info("Cant change network priority from empty list.")
            return

        # If there is a single interface without metric, make it the highest priority
        if len(interfaces) == 1 and interfaces[0].priority is None:
            interfaces[0].priority = 0

        current_priority = interfaces[0].priority or EthernetManager.default_dhcpdc_metric
        lines = []
        lines.append(f"{self.dhcpcd_conf_start_string}\n")
        for interface in interfaces:
            # Enforce priority if it's none, otherwise track new priority
            interface.priority = interface.priority or current_priority
            current_priority = interface.priority

            lines.append(f"interface {interface.name}\n")
            lines.append(f"    metric {interface.priority}\n")
            current_priority += 1000
            logger.info(f"Set current priority for {interface.name} as {interface.priority}")
        lines.append(f"{self.dhcpcd_conf_end_string}\n")

        with open("/etc/dhcpcd.conf", "a+", encoding="utf-8") as f:
            f.writelines(lines)

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

    def remove_dhcp_server_from_interface(self, interface_name: str) -> DHCPServerManager:
        logger.info(f"Removing DHCP server from interface '{interface_name}'.")
        try:
            self._dhcp_servers.remove(self._dhcp_server_on_interface(interface_name))
        except ValueError:
            # If the interface does not have a DHCP server running on, no need to raise
            pass
        except Exception as error:
            raise RuntimeError("Cannot remove DHCP server from interface.") from error

    def add_dhcp_server_to_interface(self, interface_name: str, ipv4_gateway: str) -> None:
        if self._is_dhcp_server_running_on_interface(interface_name):
            self.remove_dhcp_server_from_interface(interface_name)
        if self._is_ip_on_interface(interface_name, ipv4_gateway):
            self.remove_ip(interface_name, ipv4_gateway)
        self.add_static_ip(interface_name, ipv4_gateway)
        logger.info(f"Adding DHCP server with gateway '{ipv4_gateway}' to interface '{interface_name}'.")
        self._dhcp_servers.append(DHCPServerManager(interface_name, ipv4_gateway))

    def stop(self) -> None:
        """Perform steps necessary to properly stop the manager."""
        for dhcp_server in self._dhcp_servers:
            dhcp_server.stop()

    def __del__(self) -> None:
        self.stop()
