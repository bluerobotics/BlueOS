import asyncio
import os
import re
import stat
import subprocess
import time
from argparse import ArgumentParser, Namespace
from http.client import HTTPException
from ipaddress import IPv4Address
from typing import Any, Dict, List, Optional

from commonwealth.utils.general import HostOs, get_host_os
from exceptions import FetchError, ParseError
from fastapi import status
from loguru import logger
from typedefs import (
    ConnectionStatus,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
    WifiInterface,
    WifiInterfaceCapabilities,
    WifiInterfaceMode,
    WifiInterfaceStatus,
    WifiStatus,
)
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager
from wifi_handlers.wpa_supplicant.Hotspot import HotspotManager
from wifi_handlers.wpa_supplicant.wpa_supplicant import WPASupplicant


# pylint: disable=too-many-instance-attributes
class WifiManager(AbstractWifiManager):
    wpa = WPASupplicant()
    wpa_path: Optional[str] = None

    async def can_work(self) -> bool:
        return bool(get_host_os() == HostOs.Bullseye)

    async def try_connect_to_network(self, credentials: WifiCredentials, hidden: bool = False) -> Any:
        logger.info(f"Trying to connect to '{credentials.ssid}'.")

        network_id: Optional[int] = None
        is_new_network = False
        try:
            saved_networks = await self.get_saved_wifi_network()
            match_network = next(filter(lambda network: network.ssid == credentials.ssid, saved_networks))
            network_id = match_network.networkid
            logger.info(f"Network is already known, id={network_id}.")
        except StopIteration:
            logger.info("Network is not known.")
            is_new_network = True

        is_secure = False
        try:
            available_networks = await self.get_wifi_available()
            scanned_network = next(filter(lambda network: network.ssid == credentials.ssid, available_networks))
            flags_for_passwords = ["WPA", "WEP", "WSN"]
            for candidate in flags_for_passwords:
                if candidate in scanned_network.flags:
                    is_secure = True
                    break
        except StopIteration:
            logger.info("Could not find wifi network around.")

        if credentials.password == "" and network_id is None and is_secure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No password received and network not found among saved ones.",
            )

        try:
            # Update known network if password is not necessary anymore
            if network_id is not None and not is_secure and credentials.password == "":
                logger.info(f"Removing old entry for known network, id={network_id}.")
                await self.remove_network_by_id(network_id)
                network_id = await self.add_network(credentials, hidden)
                logger.info(f"Network entry updated, id={network_id}.")

            if network_id is None:
                network_id = await self.add_network(credentials, hidden)
                logger.info(f"Saving new network entry, id={network_id}.")

            logger.info("Performing network connection.")
            if network_id is None:
                raise ValueError("Missing 'network_id' for network connection.")
            await self.connect_to_network(network_id, timeout=40)
        except ConnectionError as error:
            if is_new_network and network_id is not None:
                logger.info("Removing new network entry since connection failed.")
                await self.remove_network_by_id(network_id)
            raise error
        logger.info(f"Successfully connected to '{credentials.ssid}'.")

    async def connect(self, path: Any) -> None:
        """Does the connection with wpa_supplicant service

        Arguments:
            path {[tuple/str]} -- Can be a tuple to connect (ip/port) or unix socket file
        """
        self.wpa.run(path)
        self._scan_task: Optional[asyncio.Task[bytes]] = None
        self._updated_scan_results: Optional[List[ScannedWifiNetwork]] = None
        self._ignored_reconnection_networks: List[str] = []
        self.connection_status = ConnectionStatus.UNKNOWN
        self._time_last_scan = 0.0

        # Perform first scan so the wlan interface gets configured (for just-flashed-images)
        await self.get_wifi_available()

        try:
            self._hotspot: Optional[HotspotManager] = None
            self._hotspot_managers: Dict[str, HotspotManager] = {}
            self._hotspot_interface: Optional[str] = None
            self._interface_modes: Dict[str, "WifiInterfaceMode"] = {}
            ssid, password = (
                self._settings_manager.settings.hotspot_ssid,
                self._settings_manager.settings.hotspot_password,
            )
            if ssid is not None and password is not None:
                await self.set_hotspot_credentials(WifiCredentials(ssid=ssid, password=password))
            if self.hotspot.supports_hotspot and self._settings_manager.settings.hotspot_enabled in [True, None]:
                time.sleep(5)
                await self.enable_hotspot()
        except Exception:
            logger.exception("Could not load previous hotspot settings.")

    @staticmethod
    def __decode_escaped(data: bytes) -> str:
        """Decode escaped byte array
        For more info: https://stackoverflow.com/questions/14820429/how-do-i-decodestring-escape-in-python3
        """
        return data.decode("unicode-escape").encode("latin1").decode("utf-8")

    @staticmethod
    def __dict_from_table(table: bytes) -> List[Dict[str, Any]]:
        """Create a dict from table text

        Arguments:
            table {[bytes]} -- A byte string table provided by wpa_supplicant

        Returns:
            [list of dicts] -- A list of dicts where keys are table header values
        """
        raw_lines = table.strip().split(b"\n")

        listed_lines = []
        for raw_line in raw_lines:
            listed_lines += [raw_line.split(b"\t")]

        # Create keys from header
        try:
            temp_header = listed_lines.pop(0)[0]
            header = temp_header.replace(b" ", b"").split(b"/")
        except Exception as error:
            raise ParseError("Failed creating header to dictionary.") from error

        output: List[Any] = []
        for line in listed_lines:
            output += [{}]
            try:
                for key, value in zip(header, line):
                    output[-1][WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)
            except Exception as error:
                raise ParseError("Failed parsing dictionary data from table.") from error

        return output

    @staticmethod
    def __dict_from_list(data: bytes) -> Dict[str, Any]:
        """Create a dict from a value based list

        Arguments:
            data {[bytes]} -- A byte string list provided by wpa_supplicant

        Returns:
            [dict] -- Dict where which key is the variable value of the list
        """
        raw_lines = data.strip().split(b"\n")

        output = {}
        for line in raw_lines:
            try:
                key, value = line.split(b"=")
                output[WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)
            except Exception as error:
                raise ParseError("Failed parsing dictionary data from list.") from error

        return output

    @staticmethod
    def _get_virtual_ap_name(physical_interface: str) -> str:
        """Generate virtual AP interface name from physical interface name."""
        match = re.search(r"\d+$", physical_interface)
        if match:
            return f"uap{match.group()}"
        return "uap0"

    def _get_hotspot_manager(self, interface: str) -> HotspotManager:
        """Get or create a hotspot manager for a specific interface."""
        if interface not in self._hotspot_managers:
            try:
                virtual_ap_name = self._get_virtual_ap_name(interface)
                self._hotspot_managers[interface] = HotspotManager(
                    interface, IPv4Address("192.168.42.1"), ap_interface_name=virtual_ap_name
                )
            except Exception as error:
                raise error
        return self._hotspot_managers[interface]

    def _get_interface_name_from_path(self) -> str:
        """Extract interface name from wpa_supplicant socket path."""
        if self.wpa_path:
            # wpa_path is like /var/run/wpa_supplicant/wlan0
            return os.path.basename(self.wpa_path)
        return "wlan0"

    @property
    def hotspot(self) -> HotspotManager:
        """Get hotspot manager for default interface (backward compatible)."""
        if self._hotspot is None:
            try:
                default_interface = self._get_interface_name_from_path()
                virtual_ap_name = self._get_virtual_ap_name(default_interface)
                self._hotspot = HotspotManager(
                    default_interface, IPv4Address("192.168.42.1"), ap_interface_name=virtual_ap_name
                )
            except Exception as error:
                self._hotspot = None
                raise error
        return self._hotspot

    async def get_wifi_available(self) -> List[ScannedWifiNetwork]:
        """Get a dict from the wifi signals available"""

        async def perform_new_scan() -> None:
            try:
                # We store the scan task here so that new scan requests that happen in the interval
                # where this one is running can check when it has finished.
                # Otherwise, it could happen that a new scan is initiated before the ones waiting know
                # the previous one has finished, making them stay on the loop unnecessarily.
                self._scan_task = asyncio.create_task(self.wpa.send_command_scan(timeout=30))
                await self._scan_task
                data = await self.wpa.send_command_scan_results()
                networks_list = WifiManager.__dict_from_table(data)
                self._updated_scan_results = [ScannedWifiNetwork(**network) for network in networks_list]
                self._time_last_scan = time.time()
            except Exception as error:
                if self._scan_task is not None:
                    self._scan_task.cancel()
                self._updated_scan_results = None
                raise FetchError("Failed to fetch wifi list.") from error

        # Performs a new scan only if more than 30 seconds passed since last scan
        if time.time() - self._time_last_scan < 30:
            return self._updated_scan_results or []
        # Performs a new scan only if it's the first one or the last one is already done
        # In case there's one running already, wait for it to finish and use its result
        if self._scan_task is None or self._scan_task.done():
            await perform_new_scan()
        else:
            awaited_scan_task_name = self._scan_task.get_name()
            while self._scan_task.get_name() == awaited_scan_task_name and not self._scan_task.done():
                logger.info(f"Waiting for {awaited_scan_task_name} results.")
                await asyncio.sleep(0.5)

        if self._updated_scan_results is None:
            raise FetchError("Failed to fetch wifi list.")

        return self._updated_scan_results

    async def get_saved_wifi_network(self) -> List[SavedWifiNetwork]:
        """Get a list of saved wifi networks"""
        try:
            data = await self.wpa.send_command_list_networks()
            networks_list = WifiManager.__dict_from_table(data)
            return [SavedWifiNetwork(**network) for network in networks_list]
        except Exception as error:
            raise FetchError("Failed to fetch saved networks list.") from error

    async def add_network(self, credentials: WifiCredentials, hidden: bool = False) -> int:
        """Set network ssid and password

        Arguments:
            credentials {[WifiCredentials]} -- object containing ssid and password of the network
            hidden {bool} -- Should be set as true when adding hidden networks (networks that do not broadcast
            the SSID, or on other words, that have SSID as blank or null on the scan results). False by default.
        """
        try:
            network_number = await self.wpa.send_command_add_network()

            await self.wpa.send_command_set_network(network_number, "ssid", f'"{credentials.ssid}"')
            if not credentials.password:
                await self.wpa.send_command_set_network(network_number, "key_mgmt", "NONE")
            else:
                await self.wpa.send_command_set_network(network_number, "psk", f'"{credentials.password}"')
            if hidden:
                await self.wpa.send_command_set_network(network_number, "scan_ssid", "1")
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
            return int(network_number)
        except Exception as error:
            raise ConnectionError("Failed to set new network.") from error

    async def remove_network_by_id(self, network_id: int) -> None:
        try:
            await self.wpa.send_command_remove_network(network_id)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
        except Exception as error:
            raise ConnectionError("Failed to remove existing network.") from error

    async def remove_network(self, ssid: str) -> None:
        """Remove saved wifi network

        Arguments:
            network_id {int} -- Network ID as it comes from WPA Supplicant list of saved networks
        """
        saved_networks = await self.get_saved_wifi_network()
        # Here we get all networks that match the ssid
        # and get a list where the biggest networkid comes first.
        # If we remove the lowest numbers first, it'll change the highest values to -1
        # TODO: We should move the entire wifi framestack to work with bssid
        match_networks = [network for network in saved_networks if network.ssid == ssid]
        match_networks = sorted(match_networks, key=lambda network: network.networkid, reverse=True)
        for match_network in match_networks:
            logger.info(f"removing (networkid={match_network.networkid})")
            await self.remove_network_by_id(match_network.networkid)

    async def connect_to_network(self, network_id: int, timeout: float = 20.0) -> None:
        """Connect to wifi network

        Arguments:
            network_id {int} -- Network ID provided by WPA Supplicant
        """
        self.connection_status = ConnectionStatus.CONNECTING
        was_hotspot_enabled = self.hotspot.is_running()
        try:
            if was_hotspot_enabled:
                await self.disable_hotspot(save_settings=False)
            await self.wpa.send_command_select_network(network_id)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
            await self.wpa.send_command_reconnect()
            start_time = time.time()
            while True:
                wpa_status = await self.status()
                is_connected = wpa_status.wpa_state == "COMPLETED"
                if is_connected:
                    current_network = await self.get_current_network()
                    if current_network and current_network.networkid == network_id:
                        break
                    raise RuntimeError("Association or authentication failed.")
                timer = time.time() - start_time
                if timer > timeout:
                    raise RuntimeError("Could not stablish a wifi connection in time.")
                await asyncio.sleep(2.0)

            # Remove network from ignored list if user deliberately connected
            current_network = await self.get_current_network()
            if current_network and current_network.ssid in self._ignored_reconnection_networks:
                logger.debug(f"Removing '{current_network.ssid}' from ignored list.")
                self._ignored_reconnection_networks.remove(current_network.ssid)
            self.connection_status = ConnectionStatus.JUST_CONNECTED
        except Exception as error:
            self.connection_status = ConnectionStatus.UNKNOWN
            raise ConnectionError(f"Failed to connect to network. {error}") from error
        finally:
            if was_hotspot_enabled:
                await self.enable_hotspot(save_settings=False)

    async def status(self) -> WifiStatus:
        """Check wpa_supplicant status"""
        try:
            data = await self.wpa.send_command_status()
            return WifiStatus(**WifiManager.__dict_from_list(data))
        except Exception as error:
            raise FetchError("Failed to get status from wifi manager.") from error

    async def reconfigure(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        try:
            await self.wpa.send_command_reconfigure()
        except Exception as error:
            raise RuntimeError("Failed to reconfigure wifi manager.") from error

    async def disconnect(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        self.connection_status = ConnectionStatus.DISCONNECTING
        try:
            # Save current network in ignored list so the watchdog doesn't auto-reconnect to it
            current_network = await self.get_current_network()
            if current_network:
                logger.debug(f"Adding '{current_network.ssid}' to ignored list.")
                self._ignored_reconnection_networks.append(current_network.ssid)
                await self.wpa.send_command_disable_network(current_network.networkid)

            await self.wpa.send_command_disconnect()
            self.connection_status = ConnectionStatus.JUST_DISCONNECTED
        except Exception as error:
            self.connection_status = ConnectionStatus.UNKNOWN
            raise ConnectionError("Failed to disconnect from wifi network.") from error

    async def enable_saved_networks(self, ignore: Optional[List[str]] = None) -> None:
        """Enable saved networks."""
        try:
            saved_networks = await self.get_saved_wifi_network()
            for network in saved_networks:
                if ignore and network.ssid in ignore:
                    continue
                await self.wpa.send_command_enable_network(network.networkid)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
        except Exception as error:
            raise RuntimeError("Failed to enable saved networks.") from error

    async def get_current_network(self) -> Optional[SavedWifiNetwork]:
        """Get current network, if connected."""
        try:
            saved_networks = await self.get_saved_wifi_network()
            for network in saved_networks:
                if network.flags is not None and "current" in network.flags.lower():
                    return network
            return None
        except Exception as error:
            raise RuntimeError("Failed to get current network.") from error

    def trigger_dhcp_client(self) -> None:
        """Trigger dhclient to get an IP address."""
        # Use the configured socket name (interface) instead of hardcoded wlan0
        interface = getattr(self, "args", None) and getattr(self.args, "socket_name", None)
        if interface:
            subprocess.run(["dhcpcd", "-n", interface], check=False)
        else:
            # Fallback to wlan0 for backward compatibility
            subprocess.run(["dhcpcd", "-n", "wlan0"], check=False)

    async def auto_reconnect(self, seconds_before_reconnecting: float) -> None:
        """Re-enable all saved networks if disconnected for more than specified time.
        When a connection is made, using the 'select' wpa command, all other saved networks are disabled, to ensure
        connection to the desired network. This prevents the system from reconnecting to one of those networks when
        away from the last connected one.

        This watchdog re-enable all connections after a specified time to ensure the system don't stay disconnected
        forever even if there are known networks nearby.

        Arguments:
            seconds_before_reconnecting {float} -- Seconds to wait disconnected before enabling all saved networks.
        """
        seconds_disconnected = 0.0
        networks_reenabled = False
        was_connected = False
        logger.debug("Watchdog starting disconnected.")
        time_disconnection = time.time()
        while True:
            await asyncio.sleep(2.5)

            # Disable watchdog checks while deliberately connecting or disconnecting
            if self.connection_status in [ConnectionStatus.CONNECTING, ConnectionStatus.DISCONNECTING]:
                continue

            is_connected = await self.get_current_network() is not None

            if is_connected and (await self.status()).ip_address is None:
                # we are connected but have no ip addres? lets ask cable-guy for a new ip
                self.trigger_dhcp_client()

            if was_connected and not is_connected:
                self.connection_status = ConnectionStatus.JUST_DISCONNECTED
                time_disconnection = time.time()
                was_connected = False
                logger.debug("Lost connection.")
            elif not was_connected and not is_connected:
                self.connection_status = ConnectionStatus.STILL_DISCONNECTED
                seconds_disconnected = time.time() - time_disconnection
                logger.debug(f"{int(seconds_disconnected)} seconds passed since disconnection.")
            elif not was_connected and is_connected:
                self.connection_status = ConnectionStatus.JUST_CONNECTED
                seconds_disconnected = 0
                networks_reenabled = False
                was_connected = True
                logger.debug("Regained connection.")
            else:
                self.connection_status = ConnectionStatus.STILL_CONNECTED

            if not networks_reenabled and seconds_disconnected >= seconds_before_reconnecting:
                logger.debug("Watchdog activated.")
                logger.debug("Trying to reconnect to available networks.")
                await self.enable_saved_networks(self._ignored_reconnection_networks)
                await self.wpa.send_command_reconnect()
                try:
                    if self._settings_manager.settings.smart_hotspot_enabled in [None, True]:
                        logger.debug("Starting smart-hotspot.")
                        await self.enable_hotspot()
                except Exception:
                    logger.exception("Could not start smart-hotspot.")
                networks_reenabled = True

    async def start_hotspot_watchdog(self) -> None:
        logger.debug("Starting hotspot watchdog.")
        if not self.hotspot.supports_hotspot:
            logger.debug("Hotspot is not supported. Stopping watchdog.")
            return
        while True:
            await asyncio.sleep(30)
            try:
                if self._settings_manager.settings.hotspot_enabled and not self.hotspot.is_running():
                    logger.warning("Hotspot should be working but is not. Restarting it.")
                    await self.enable_hotspot()
            except Exception:
                logger.exception("Could not start hotspot from the watchdog routine.")

    async def set_hotspot_credentials(self, credentials: WifiCredentials) -> None:
        self._settings_manager.settings.hotspot_ssid = credentials.ssid
        self._settings_manager.settings.hotspot_password = credentials.password
        self._settings_manager.save()

        self.hotspot.set_credentials(credentials)

        if self.hotspot.is_running():
            await self.disable_hotspot(save_settings=False)
            time.sleep(5)
            await self.enable_hotspot(save_settings=False)

    def hotspot_credentials(self) -> WifiCredentials:
        credentials: WifiCredentials = self.hotspot.credentials
        return credentials

    async def enable_hotspot(self, save_settings: bool = True) -> bool:
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = True
            self._settings_manager.save()

        if self.hotspot.is_running():
            logger.warning("Hotspot already running. No need to enable it again.")
        await self.hotspot.start()
        return True

    async def disable_hotspot(self, save_settings: bool = True) -> None:
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = False
            self._settings_manager.save()

        self.hotspot.stop()

    async def enable_hotspot_on_interface(self, interface: str, save_settings: bool = True) -> bool:
        """Enable hotspot on a specific interface."""
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = True
            self._settings_manager.save()

        hotspot_manager = self._get_hotspot_manager(interface)
        if hotspot_manager.is_running():
            logger.warning(f"Hotspot already running on {interface}.")
        await hotspot_manager.start()
        self._hotspot_interface = interface
        return True

    async def disable_hotspot_on_interface(self, interface: str, save_settings: bool = True) -> None:
        """Disable hotspot on a specific interface."""
        if interface in self._hotspot_managers:
            self._hotspot_managers[interface].stop()
            if self._hotspot_interface == interface:
                self._hotspot_interface = None

        if save_settings and not any(m.is_running() for m in self._hotspot_managers.values()):
            self._settings_manager.settings.hotspot_enabled = False
            self._settings_manager.save()

    async def hotspot_is_running_on_interface(self, interface: str) -> bool:
        """Check if hotspot is running on a specific interface."""
        if interface in self._hotspot_managers:
            return self._hotspot_managers[interface].is_running()
        return False

    async def get_hotspot_interface(self) -> Optional[str]:
        """Get the interface currently running hotspot, or None if no hotspot is running."""
        for interface, manager in self._hotspot_managers.items():
            if manager.is_running():
                return interface
        if self._hotspot is not None and self._hotspot.is_running():
            return self._get_interface_name_from_path()
        return None

    async def supports_hotspot_on_interface(self, interface: str) -> bool:
        """Check if hotspot is supported on a specific interface."""
        try:
            hotspot_manager = self._get_hotspot_manager(interface)
            return hotspot_manager.supports_hotspot
        except Exception:
            return False

    def enable_smart_hotspot(self) -> None:
        self._settings_manager.settings.smart_hotspot_enabled = True
        self._settings_manager.save()

    def disable_smart_hotspot(self) -> None:
        self._settings_manager.settings.smart_hotspot_enabled = False
        self._settings_manager.save()

    def is_smart_hotspot_enabled(self) -> bool:
        return self._settings_manager.settings.smart_hotspot_enabled is True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        adds custom entries to argparser
        """
        parser.add_argument(
            "--socket",
            dest="socket_name",
            type=str,
            help="Name of the WPA Supplicant socket. Usually 'wlan0' or 'wlp4s0'.",
        )

    def configure(self, args: Namespace) -> None:
        self.args = args

    async def start(self) -> None:
        wpa_socket_folder = "/var/run/wpa_supplicant/"
        try:
            if self.args.socket_name:
                logger.info("Connecting via provided socket.")
                socket_name = self.args.socket_name
            else:
                logger.info("Connecting via default socket.")

                def is_socket(file_path: str) -> bool:
                    try:
                        mode = os.stat(file_path).st_mode
                        return stat.S_ISSOCK(mode)
                    except Exception as error:
                        logger.warning(f"Could not check if '{file_path}' is a socket: {error}")
                        return False

                # We are going to sort and get the latest file, since this in theory will be an external interface
                # added by the user
                entries = os.scandir(wpa_socket_folder)
                available_sockets = sorted(
                    [
                        entry.path
                        for entry in entries
                        if entry.name.startswith(("wlan", "wifi", "wlp")) and is_socket(entry.path)
                    ]
                )
                if not available_sockets:
                    raise RuntimeError("No wifi sockets available.")
                socket_name = available_sockets[-1]
                logger.info(f"Going to use {socket_name} file")
            WLAN_SOCKET = os.path.join(wpa_socket_folder, socket_name)
            self.wpa_path = WLAN_SOCKET
            await self.connect(WLAN_SOCKET)
        except Exception as socket_connection_error:
            logger.warning(f"Could not connect with wifi socket. {socket_connection_error}")
            logger.info("Connecting via internet wifi socket.")
            try:
                await self.connect(("127.0.0.1", 6664))
            except Exception as udp_connection_error:
                logger.error(f"Could not connect with internet socket: {udp_connection_error}. Exiting.")
                raise udp_connection_error
        loop = asyncio.get_event_loop()
        loop.create_task(self.auto_reconnect(60))
        loop.create_task(self.start_hotspot_watchdog())

    async def supports_hotspot(self) -> bool:
        return self.hotspot.supports_hotspot

    async def hotspot_is_running(self) -> bool:
        return self.hotspot.is_running()

    async def get_wifi_interfaces(self) -> List[WifiInterface]:
        interface_name = self._get_interface_name_from_path()
        wifi_status = await self.status()

        supports_ap = await self.supports_hotspot_on_interface(interface_name)
        current_mode = self._interface_modes.get(interface_name, WifiInterfaceMode.NORMAL)
        is_connected = wifi_status.wpa_state == "COMPLETED"

        return [
            WifiInterface(
                name=interface_name,
                connected=is_connected,
                ssid=wifi_status.ssid,
                signal_strength=None,
                ip_address=wifi_status.ip_address,
                mac_address=None,
                mode=current_mode,
                supports_hotspot=supports_ap,
                supports_dual_mode=supports_ap,
            )
        ]

    async def get_all_interface_status(self) -> List[WifiInterfaceStatus]:
        interface_name = self._get_interface_name_from_path()
        wifi_status = await self.status()
        is_connected = wifi_status.wpa_state == "COMPLETED"

        return [
            WifiInterfaceStatus(
                interface=interface_name,
                state="connected" if is_connected else "disconnected",
                ssid=wifi_status.ssid,
                bssid=wifi_status.bssid,
                ip_address=wifi_status.ip_address,
                signal_strength=None,
                frequency=int(wifi_status.freq) if wifi_status.freq else None,
                key_mgmt=wifi_status.key_mgmt,
            )
        ]

    async def get_interface_capabilities(self, interface: str) -> WifiInterfaceCapabilities:
        supports_ap = await self.supports_hotspot_on_interface(interface)
        current_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)

        available_modes = [WifiInterfaceMode.NORMAL]
        if supports_ap:
            available_modes.append(WifiInterfaceMode.HOTSPOT)
            available_modes.append(WifiInterfaceMode.DUAL)

        return WifiInterfaceCapabilities(
            interface=interface,
            supports_ap_mode=supports_ap,
            supports_dual_mode=supports_ap,
            current_mode=current_mode,
            available_modes=available_modes,
        )

    def get_interface_mode(self, interface: str) -> WifiInterfaceMode:
        return self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)

    async def set_interface_mode(self, interface: str, mode: WifiInterfaceMode) -> bool:
        caps = await self.get_interface_capabilities(interface)
        if mode not in caps.available_modes:
            raise ValueError(f"Mode {mode} not supported on {interface}. Available: {caps.available_modes}")

        if mode == WifiInterfaceMode.NORMAL:
            await self.disable_hotspot_on_interface(interface)
            self._interface_modes[interface] = mode
            return True
        if mode == WifiInterfaceMode.HOTSPOT:
            result = await self.enable_hotspot_on_interface(interface)
            if result:
                self._interface_modes[interface] = mode
            return result
        # mode == WifiInterfaceMode.DUAL
        result = await self.enable_hotspot_on_interface(interface)
        if result:
            self._interface_modes[interface] = mode
        return result
