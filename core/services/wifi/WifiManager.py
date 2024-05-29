import asyncio
import time
from ipaddress import IPv4Address
from typing import Any, Dict, List, Optional

from commonwealth.settings.manager import Manager
from commonwealth.utils.commands import run_command
from loguru import logger

from exceptions import FetchError, ParseError
from Hotspot import HotspotManager
from settings import SettingsV1
from typedefs import (
    ConnectionStatus,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
)
from wpa_supplicant import WPASupplicant


class WifiManager:
    wpa = WPASupplicant()

    def connect(self, path: Any) -> None:
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
        asyncio.run(self.get_wifi_available())

        self._settings_manager = Manager("wifi-manager", SettingsV1)
        self._settings_manager.load()
        try:
            self._hotspot: Optional[HotspotManager] = None
            ssid, password = (
                self._settings_manager.settings.hotspot_ssid,
                self._settings_manager.settings.hotspot_password,
            )
            if ssid is not None and password is not None:
                self.set_hotspot_credentials(WifiCredentials(ssid=ssid, password=password))
            if self._settings_manager.settings.hotspot_enabled in [True, None]:
                time.sleep(5)
                self.enable_hotspot()
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

    @property
    def hotspot(self) -> HotspotManager:
        if self._hotspot is None:
            try:
                self._hotspot = HotspotManager("wlan0", IPv4Address("192.168.42.1"))
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
            return network_number
        except Exception as error:
            raise ConnectionError("Failed to set new network.") from error

    async def remove_network(self, network_id: int) -> None:
        """Remove saved wifi network

        Arguments:
            network_id {int} -- Network ID as it comes from WPA Supplicant list of saved networks
        """
        try:
            await self.wpa.send_command_remove_network(network_id)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
        except Exception as error:
            raise ConnectionError("Failed to remove existing network.") from error

    async def connect_to_network(self, network_id: int, timeout: float = 20.0) -> None:
        """Connect to wifi network

        Arguments:
            network_id {int} -- Network ID provided by WPA Supplicant
        """
        self.connection_status = ConnectionStatus.CONNECTING
        was_hotspot_enabled = self.hotspot.is_running()
        try:
            if was_hotspot_enabled:
                self.disable_hotspot(save_settings=False)
            await self.wpa.send_command_select_network(network_id)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
            await self.wpa.send_command_reconnect()
            start_time = time.time()
            while True:
                status = await self.status()
                is_connected = status.get("wpa_state") == "COMPLETED"
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
                self.enable_hotspot(save_settings=False)

    async def status(self) -> Dict[str, Any]:
        """Check wpa_supplicant status"""
        try:
            data = await self.wpa.send_command_status()
            return WifiManager.__dict_from_list(data)
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
            if is_connected and "ip_address" not in await self.status():
                # we are connected but have no ip addres? lets try calling dhclient manually
                run_command("sudo dhclient wlan0", check=False)

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
                        self.enable_hotspot()
                except Exception:
                    logger.exception("Could not start smart-hotspot.")
                networks_reenabled = True

    async def start_hotspot_watchdog(self) -> None:
        logger.debug("Starting hotspot watchdog.")
        while True:
            await asyncio.sleep(30)
            try:
                if self._settings_manager.settings.hotspot_enabled and not self.hotspot.is_running():
                    logger.warning("Hotspot should be working but is not. Restarting it.")
                    self.enable_hotspot()
            except Exception:
                logger.exception("Could not start hotspot from the watchdog routine.")

    def set_hotspot_credentials(self, credentials: WifiCredentials) -> None:
        self._settings_manager.settings.hotspot_ssid = credentials.ssid
        self._settings_manager.settings.hotspot_password = credentials.password
        self._settings_manager.save()

        self.hotspot.set_credentials(credentials)

        if self.hotspot.is_running():
            self.disable_hotspot(save_settings=False)
            time.sleep(5)
            self.enable_hotspot(save_settings=False)

    def hotspot_credentials(self) -> WifiCredentials:
        return self.hotspot.credentials

    def enable_hotspot(self, save_settings: bool = True) -> None:
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = True
            self._settings_manager.save()

        if self.hotspot.is_running():
            logger.warning("Hotspot already running. No need to enable it again.")
            return
        self.hotspot.start()

    def disable_hotspot(self, save_settings: bool = True) -> None:
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = False
            self._settings_manager.save()

        self.hotspot.stop()

    def enable_smart_hotspot(self) -> None:
        self._settings_manager.settings.smart_hotspot_enabled = True
        self._settings_manager.save()

    def disable_smart_hotspot(self) -> None:
        self._settings_manager.settings.smart_hotspot_enabled = False
        self._settings_manager.save()
