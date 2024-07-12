import os
import time
from typing import List

import sdbus
from loguru import logger
from sdbus_block.networkmanager import (
    NetworkConnectionSettings,
    NetworkDeviceGeneric,
    NetworkManager,
    NetworkManagerSettings,
)
from sdbus_block.networkmanager.settings.datatypes import AddressData

from typedefs import NetworkInterfaceMetric, NetworkInterfaceMetricApi

sdbus.set_default_bus(sdbus.sd_bus_open_system())

network_manager = NetworkManager()


class AbstractNetworkHandler:
    def __init__(self) -> None:
        pass

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


class NetworkManagerHandler(AbstractNetworkHandler):
    def detect(self) -> bool:
        try:
            all_devices = {path: NetworkDeviceGeneric(path) for path in network_manager.devices}
            return bool(len(all_devices))
        except Exception as error:
            logger.error(f"Failed to detect NetworkManager: {error}")
            return False

    def remove_static_ip(self, interface_name: str, ip: str) -> None:
        networkmanager_settings = NetworkManagerSettings()
        for connection_path in networkmanager_settings.connections:
            try:
                settings = NetworkConnectionSettings(connection_path)
                data = settings.get_profile()
                if data.connection.interface_name != interface_name:
                    continue
                ips = data.ipv4.address_data
                data.ipv4.address_data = [addressData for addressData in ips if ip not in addressData.address]
                settings.update_profile(data)
                network_manager.activate_connection(connection_path)
            except Exception as e:
                logger.error(f"Failed to remove static ip {ip} for {interface_name}: {e}")

    def add_static_ip(self, interface_name: str, ip: str) -> None:
        networkmanager_settings = NetworkManagerSettings()

        time.sleep(1)
        for connection_path in networkmanager_settings.connections:
            try:
                settings = NetworkConnectionSettings(connection_path)
                data = settings.get_profile()
                if data.connection.interface_name != interface_name:
                    continue
                if any(ip in addressData.address for addressData in data.ipv4.address_data):
                    logger.info(f"IP {ip} already exists for {interface_name}")
                    continue
                new_ip = AddressData(address=ip, prefix=24)
                data.ipv4.address_data.append(new_ip)
                settings.update_profile(data)
                network_manager.activate_connection(connection_path)
                return
            except Exception as e:
                logger.error(f"Failed to set static ip {ip} for {interface_name}: {e}")

    def enable_dhcp_client(self, interface_name: str) -> None:
        networkmanager_settings = NetworkManagerSettings()
        for connection_path in networkmanager_settings.connections:
            settings = NetworkConnectionSettings(connection_path)
            properties = settings.get_settings()
            if properties["connection"]["interface-name"][1] != interface_name:
                continue
            properties["ipv4"]["method"] = ("s", "auto")
            settings.update(properties)
            network_manager.activate_connection(connection_path)

    def get_interfaces_priority(self) -> List[NetworkInterfaceMetric]:
        interfaces = []
        networkmanager_settings = NetworkManagerSettings()
        for dbus_connection_path in networkmanager_settings.connections:
            profile = NetworkConnectionSettings(dbus_connection_path).get_profile()
            if profile.connection.interface_name and profile.ipv4.route_metric:
                interfaces.append(
                    NetworkInterfaceMetric(
                        index=0, name=profile.connection.interface_name, priority=profile.ipv4.route_metric
                    )
                )
        return interfaces

    def set_interfaces_priority(self, interfaces: List[NetworkInterfaceMetricApi]) -> None:
        metric = interfaces[0].priority or 1000
        for interface in interfaces:
            networkmanager_settings = NetworkManagerSettings()
            for connection_path in networkmanager_settings.connections:
                settings = NetworkConnectionSettings(connection_path)
                properties = settings.get_settings()
                if properties["connection"]["interface-name"][1] != interface.name:
                    continue
                properties["ipv4"]["route-metric"] = ("u", metric)
                metric += 1000
                logger.info(f"Settting current priority for {interface.name} as {metric}")
                settings.update(properties)
                network_manager.activate_connection(connection_path)


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


class NetworkHandlerDetector:
    def __iinit__(self) -> None:
        pass

    def getHandler(self) -> AbstractNetworkHandler:
        for candidate in AbstractNetworkHandler.__subclasses__():
            if candidate().detect():
                logger.info(f"Detected network handler: {candidate.__name__}")
                return candidate()
        raise RuntimeError("No network handler detected")
