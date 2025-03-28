import os
import re
import socket
from typing import Any, List

import sdbus
from loguru import logger
from pyroute2 import IPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from sdbus_async.networkmanager import (
    NetworkConnectionSettings,
    NetworkDeviceGeneric,
    NetworkManager,
    NetworkManagerSettings,
)

from typedefs import NetworkInterfaceMetricApi

sdbus.set_default_bus(sdbus.sd_bus_open_system())

network_manager = NetworkManager()


class AbstractNetworkHandler:
    def __init__(self) -> None:
        self.ipr = IPRoute()

    async def detect(self) -> bool:
        raise NotImplementedError("NetworkManager does not support detecting network interfaces priority")

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        raise NotImplementedError("NetworkManager does not support setting interface priority")

    def enable_dhcp_client(self, interface_name: str) -> None:
        pass

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
            logger.info(f"Added IP '{ip}' to interface '{interface_name}'.")
        except Exception as error:
            logger.error(f"Failed to add IP '{ip}' to interface '{interface_name}'. {error}")

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        pass

    async def cleanup_interface_connections(self, interface_name: str) -> None:
        pass

    def _update_route(self, interface_name: str, interface_index: int, route: Any, priority: int) -> None:
        """Update a single route with new priority.

        Args:
            interface_name: Name of the interface
            interface_index: Index of the interface
            route: Route object
            priority: New priority to set
        """
        # Skip non-default routes (those not pointing to 0.0.0.0/0)
        dst = route.get_attr("RTA_DST")
        if dst is not None:  # If dst is None, it's a default route (0.0.0.0/0)
            return
        if route.get_attr("RTA_PRIORITY") == priority:
            return

        self.ipr.route(
            "del",
            oif=interface_index,
            family=socket.AF_INET,
            scope=route["scope"],
            proto=route["proto"],
            type=route["type"],
            dst="0.0.0.0/0",  # For default route
            gateway=route.get_attr("RTA_GATEWAY"),
            table=route.get_attr("RTA_TABLE", 254),  # Default to main table if not specified
        )

        for attempt in range(3):
            try:
                # Add the new route with updated priority
                logger.info(f"Adding new route for {interface_name} with priority {priority}")
                self.ipr.route(
                    "add",
                    oif=interface_index,
                    family=socket.AF_INET,
                    scope=route["scope"],
                    proto=route["proto"],
                    type=route["type"],
                    dst="0.0.0.0/0",  # For default route
                    gateway=route.get_attr("RTA_GATEWAY"),
                    priority=priority + attempt,
                    table=route.get_attr("RTA_TABLE", 254),  # Default to main table if not specified
                )
                logger.info(f"Updated default route for {interface_name} with priority {priority}")
                break
            except Exception as e:
                logger.error(f"Failed to update route for {interface_name}: {e} (attempt {attempt})")

    def trigger_dynamic_ip_acquisition(self, interface_name: str) -> str | None:
        """Run dhclient to get a new IP address and return it.

        Args:
            interface_name: Name of the interface to get IP for

        Returns:
            The IP address acquired from DHCP, or None if failed
        """
        try:
            # Just run dhclient without releasing existing IPs
            command = f"timeout 5 dhclient -d -v {interface_name} 2>&1 || echo 'timeout'"
            logger.info(f"Running: {command}")
            dhclient_output = os.popen(command).read()

            # Check if timeout occurred
            if "timeout" in dhclient_output:
                logger.info(f"dhclient timed out for interface {interface_name}.")
                return None

            bound_ip_match = re.search(r"bound to ([0-9.]+)", dhclient_output)
            if bound_ip_match:
                logger.info(f"Got new IP {bound_ip_match.group(1)} from DHCP for {interface_name}")
                return bound_ip_match.group(1)

            logger.error(f"Could not find bound IP in dhclient output: {dhclient_output}")
            return None

        except Exception as e:
            logger.error(f"Failed to run dhclient: {e}")
            return None

    def set_interfaces_priority_using_ipr(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        if not interfaces:
            logger.info("No interfaces to set priority for")
            return

        for interface in interfaces:
            try:
                # Use specified priority or increment current_priority
                priority = interface.priority

                # Get interface index
                interface_index = self.ipr.link_lookup(ifname=interface.name)[0]

                # Get all routes for this interface
                routes = self.ipr.get_routes(oif=interface_index, family=socket.AF_INET)

                # Update existing routes
                for route in routes:
                    try:
                        self._update_route(interface.name, interface_index, route, priority)
                    except Exception as e:
                        logger.error(f"Failed to update route for {interface.name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Failed to set priority for interface {interface.name}: {e}")
                continue


class BookwormHandler(AbstractNetworkHandler):
    """
    While this class requires NetworkManager, it does NOT use NetworkManager for controlling the interfaces.
    Instead it uses the Bookworm-specific NetworkManagerSettings API to remove the connections.
    It then relies on IPRoute, dhclient, and dnsmasq to manage the interfaces.
    """

    async def cleanup_interface_connections(self, interface_name: str) -> None:
        network_manager_settings = NetworkManagerSettings()
        for connection_path in await network_manager_settings.connections:
            profile = NetworkConnectionSettings(connection_path).get_profile()
            # Skip if this is a wireless connection
            profile_connection = (await profile).connection
            if profile_connection.connection_type == "802-11-wireless":
                continue
            if profile_connection.interface_name == interface_name:
                logger.info(
                    f"Removing connection {profile_connection.uuid} ({profile_connection.connection_id}) for interface {interface_name}"
                )
                try:
                    await NetworkManagerSettings().delete_connection_by_uuid(profile_connection.uuid)
                except Exception as e:
                    logger.error(
                        f"Failed to remove connection {profile_connection.uuid} ({profile_connection.connection_id}) for interface {interface_name}: {e}"
                    )

    async def detect(self) -> bool:
        try:

            all_devices = {path: NetworkDeviceGeneric(path) for path in await network_manager.get_devices()}
            return bool(len(all_devices))
        except Exception as error:
            logger.error(f"Failed to detect NetworkManager: {error}")
            return False

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        interface_index = self.ipr.link_lookup(ifname=interface_name)[0]
        self.ipr.addr("del", index=interface_index, address=ip, prefixlen=24)

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        """Sets network interface priority using IPRoute.

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics,
                sorted by priority to set.
        """
        self.set_interfaces_priority_using_ipr(interfaces)

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

    async def detect(self) -> bool:
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
        """Sets network interface priority..

        Args:
            interfaces (List[NetworkInterfaceMetricApi]): A list of interfaces and their priority metrics.
        """

        self.set_interfaces_priority_using_ipr(interfaces)

        self._remove_dhcpcd_configuration()

        # Update interfaces priority if possible
        if not interfaces:
            logger.info("Cant change network priority from empty list.")
            return

        current_priority = interfaces[0].priority
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

    async def getHandler(self) -> AbstractNetworkHandler:
        for candidate in AbstractNetworkHandler.__subclasses__():
            if await candidate().detect():
                logger.info(f"Detected network handler: {candidate.__name__}")
                return candidate()
        raise RuntimeError("No network handler detected")
