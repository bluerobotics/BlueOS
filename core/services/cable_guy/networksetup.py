import os
import re
import socket
from typing import Dict, List

import sdbus
from loguru import logger
from pyroute2 import IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from sdbus_block.networkmanager import (
    NetworkConnectionSettings,
    NetworkDeviceGeneric,
    NetworkManager,
    NetworkManagerSettings,
)

from typedefs import NetworkInterfaceMetric, NetworkInterfaceMetricApi

sdbus.set_default_bus(sdbus.sd_bus_open_system())

network_manager = NetworkManager()


class AbstractNetworkHandler:
    def __init__(self) -> None:
        self.ipr = IPRoute()

    def detect(self) -> bool:
        raise NotImplementedError("NetworkManager does not support detecting network interfaces priority")

    def get_interfaces_priority(self) -> List[NetworkInterfaceMetric]:
        raise NotImplementedError("NetworkManager does not support getting network interfaces priority")

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        raise NotImplementedError("NetworkManager does not support setting interface priority")

    def enable_dhcp_client(self, interface_name: str) -> None:
        pass

    def add_static_ip(self, interface_name: str, ip: str) -> None:
        pass

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        pass

    def trigger_dynamic_ip_acquisition(self, interface_name: str) -> None:
        raise NotImplementedError("This Handler does not support setting interface priority")

    def cleanup_interface_connections(self, interface_name: str) -> None:
        pass


class BookwormHandler(AbstractNetworkHandler):
    """
    While this class requires NetworkManager, it does NOT use NetworkManager for controlling the interfaces.
    Instead it uses the Bookworm-specific NetworkManagerSettings API to remove the connections.
    It then relies on IPRoute, dhclient, and dnsmasq to manage the interfaces.
    """

    def cleanup_interface_connections(self, interface_name: str) -> None:
        network_manager_settings = NetworkManagerSettings()
        for connection_path in network_manager_settings.connections:
            profile = NetworkConnectionSettings(connection_path).get_profile()
            if profile.connection.interface_name == interface_name:
                logger.info(
                    f"Removing connection {profile.connection.uuid} ({profile.connection.connection_id}) for interface {interface_name}"
                )
                try:
                    NetworkManagerSettings().delete_connection_by_uuid(profile.connection.uuid)
                except Exception as e:
                    logger.error(
                        f"Failed to remove connection {profile.connection.uuid} ({profile.connection.connection_id}) for interface {interface_name}: {e}"
                    )

    def detect(self) -> bool:
        try:
            all_devices = {path: NetworkDeviceGeneric(path) for path in network_manager.devices}
            return bool(len(all_devices))
        except Exception as error:
            logger.error(f"Failed to detect NetworkManager: {error}")
            return False

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        interface_index = self.ipr.link_lookup(ifname=interface_name)[0]
        self.ipr.addr("del", index=interface_index, address=ip, prefixlen=24)

    def add_static_ip(self, interface_name: str, ip: str) -> None:
        """Set ip address for a specific interface if it doesn't already exist

        Args:
            interface_name (str): Interface name
            ip (str): Desired ip address
        """
        interface_index = self.ipr.link_lookup(ifname=interface_name)[0]

        # Check if IP already exists on the interface
        existing_addrs = self.ipr.get_addr(index=interface_index)
        for addr in existing_addrs:
            if addr.get_attr("IFA_ADDRESS") == ip:
                logger.info(f"IP '{ip}' already exists on interface '{interface_name}', skipping addition.")
                return

        try:
            self.ipr.addr("add", index=interface_index, address=ip, prefixlen=24)
            logger.info(f"Added static IP '{ip}' to interface '{interface_name}'.")
        except Exception as error:
            logger.error(f"Failed to add IP '{ip}' to interface '{interface_name}'. {error}")

    def get_interfaces_priority(self) -> List[NetworkInterfaceMetric]:
        """Get the priority metrics for all network interfaces using IPRoute.

        Returns:
            List[NetworkInterfaceMetric]: A list of priority metrics for each interface.
        """
        interfaces = self.ipr.get_links()
        # Get all IPv4 routes
        routes = self.ipr.get_routes(family=socket.AF_INET)

        # Create a mapping of interface index to name
        name_dict = {iface["index"]: iface.get_attr("IFLA_IFNAME") for iface in interfaces}

        # Get metrics for each interface from routes
        metric_index_list = [
            {"metric": route.get_attr("RTA_PRIORITY", 0), "index": route.get_attr("RTA_OIF")} for route in routes
        ]

        # Keep the highest metric per interface
        metric_dict: Dict[int, int] = {}
        for d in metric_index_list:
            if d["index"] in metric_dict:
                metric_dict[d["index"]] = max(metric_dict[d["index"]], d["metric"])
            else:
                metric_dict[d["index"]] = d["metric"]

        # Create NetworkInterfaceMetric objects for each interface
        result = []
        for index, name in name_dict.items():
            metric = NetworkInterfaceMetric(index=index, name=name, priority=metric_dict.get(index, 0))
            result.append(metric)

        return result

    # pylint: disable=too-many-nested-blocks
    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        """Sets network interface priority using IPRoute.

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics,
                sorted by priority to set.
        """
        if not interfaces:
            logger.info("No interfaces to set priority for")
            return

        # If there's only one interface and no priority specified, set it to highest priority (0)
        if len(interfaces) == 1 and interfaces[0].priority is None:
            interfaces[0].priority = 0

        current_priority = 1000
        for interface in interfaces:
            try:
                # Use specified priority or increment current_priority
                priority = interface.priority if interface.priority is not None else current_priority

                # Get interface index
                interface_index = self.ipr.link_lookup(ifname=interface.name)[0]

                # Get all routes for this interface
                routes = self.ipr.get_routes(oif=interface_index, family=socket.AF_INET)

                # Update existing routes
                for route in routes:
                    try:
                        route_data = {"priority": priority}

                        # Copy existing route attributes
                        for attr in ["RTA_DST", "RTA_GATEWAY", "RTA_TABLE", "RTA_PREFSRC"]:
                            value = route.get_attr(attr)
                            if value:
                                # Convert attribute name to lowercase and remove RTA_ prefix
                                key = attr.lower().replace("rta_", "")
                                route_data[key] = value

                        # Update the route
                        self.ipr.route(
                            "replace",
                            oif=interface_index,
                            family=socket.AF_INET,
                            scope=route["scope"],
                            proto=route["proto"],
                            type=route["type"],
                            **route_data,
                        )
                        logger.info(f"Updated route for {interface.name} with priority {priority}")
                    except Exception as e:
                        logger.error(f"Failed to update route for {interface.name}: {e}")
                        continue

                current_priority += 1000
            except Exception as e:
                logger.error(f"Failed to set priority for interface {interface.name}: {e}")
                continue

    def _get_dhcp_address_using_dhclient(self, interface_name: str) -> str | None:
        """Run dhclient to get a new IP address and return it.

        Args:
            interface_name: Name of the interface to get IP for

        Returns:
            The IP address acquired from DHCP, or None if failed
        """
        try:
            # Just run dhclient without releasing existing IPs
            command = f"timeout 5 dhclient -v {interface_name} 2>&1"
            logger.info(f"Running: {command}")
            dhclient_output = os.popen(command).read()

            bound_ip_match = re.search(r"bound to ([0-9.]+)", dhclient_output)
            if bound_ip_match:
                return bound_ip_match.group(1)

            logger.error(f"Could not find bound IP in dhclient output: {dhclient_output}")
            return None

        except Exception as e:
            logger.error(f"Failed to run dhclient: {e}")
            return None

    def trigger_dynamic_ip_acquisition(self, interface_name: str) -> None:
        """Get a new IP from DHCP using dhclient.
        The IP will be managed by dhclient and not added to NetworkManager's configuration.

        Args:
            interface_name: Name of the interface to get IP for
        """
        # Get new IP using dhclient
        new_ip = self._get_dhcp_address_using_dhclient(interface_name)
        if not new_ip:
            logger.error(f"Failed to get DHCP-acquired IP for {interface_name}")
            return

        logger.info(f"Got new IP {new_ip} from DHCP for {interface_name}")

    def get_interface_dynamic_ip(self, interface_name: str) -> str | None:
        """Check if the interface has any dynamic IP addresses (non-static IPs)

        Args:
            interface_name (str): Name of the interface to check

        Returns:
            str | None: The dynamic IP address if found, None otherwise
        """
        try:
            interface_index = self.ipr.link_lookup(ifname=interface_name)[0]
            addresses = self.ipr.get_addr(index=interface_index)
            for addr in addresses:
                for key, value in addr["attrs"]:
                    if key == "IFA_ADDRESS":
                        # If any IP is not static, it's dynamic
                        flags = [flag for k, flag in addr["attrs"] if k == "IFA_FLAGS"][0]
                        flag_names = ifaddrmsg.flags2names(flags)
                        if "IFA_F_PERMANENT" not in flag_names:
                            logger.debug(f"Found dynamic IP: {value}")
                            return str(value)
            logger.debug("No dynamic IP found")
            return None
        except Exception as e:
            logger.error(f"Failed to check dynamic IP for {interface_name}: {e}")
            return None


class DHCPCD(AbstractNetworkHandler):
    dhcpcd_conf_path = "/etc/dhcpcd.conf"
    dhcpcd_conf_start_string = "#blueos-interface-priority-start"
    dhcpcd_conf_end_string = "#blueos-interface-priority-end"
    # https://man.archlinux.org/man/dhcpcd.conf.5#metric
    default_dhcpdc_metric = 1000

    def detect(self) -> bool:
        return os.path.isfile("/etc/dhcpcd.conf")

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

    def get_interfaces_priority(self) -> List[NetworkInterfaceMetric]:
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
                    current_metric = self.default_dhcpdc_metric

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

    def _get_dhcp_address_using_dhclient(self, interface_name: str) -> str | None:
        """Run dhclient to get a new IP address and return it.

        Args:
            interface_name: Name of the interface to get IP for

        Returns:
            The IP address acquired from DHCP, or None if failed
        """
        try:
            # Just run dhclient without releasing existing IPs
            command = ["timeout", "5", "dhclient", "-v", interface_name]
            logger.info(f"Running: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            dhclient_output = result.stdout + result.stderr

            bound_ip_match = re.search(r"bound to ([0-9.]+)", dhclient_output)
            if bound_ip_match:
                return bound_ip_match.group(1)

            logger.error(f"Could not find bound IP in dhclient output: {dhclient_output}")
            return None

        except Exception as e:
            logger.error(f"Failed to run dhclient: {e}")
            return None

    def trigger_dynamic_ip_acquisition(self, interface_name: str) -> None:
        """Get a new IP from DHCP using dhclient.
        The IP will be managed by dhclient and not added to NetworkManager's configuration.

        Args:
            interface_name: Name of the interface to get IP for
        """
        # Get new IP using dhclient
        new_ip = self._get_dhcp_address_using_dhclient(interface_name)
        if not new_ip:
            logger.error(f"Failed to get DHCP-acquired IP for {interface_name}")
            return

        logger.info(f"Got new IP {new_ip} from DHCP for {interface_name}")

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
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

        current_priority = interfaces[0].priority or self.default_dhcpdc_metric
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

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        interface_index = self.ipr.link_lookup(ifname=interface_name)[0]
        self.ipr.addr("del", index=interface_index, address=ip, prefixlen=24)


class NetworkHandlerDetector:
    def __init__(self) -> None:
        pass

    def getHandler(self) -> AbstractNetworkHandler:
        for candidate in AbstractNetworkHandler.__subclasses__():
            if candidate().detect():
                logger.info(f"Detected network handler: {candidate.__name__}")
                return candidate()
        raise RuntimeError("No network handler detected")
