import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from exceptions import FetchError, ParseError
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
        self.connection_status = ConnectionStatus.UNKNOWN

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

    async def get_wifi_available(self) -> List[ScannedWifiNetwork]:
        """Get a dict from the wifi signals available"""

        async def perform_new_scan() -> None:
            try:
                # We store the scan task here so that new scan requests that happen in the interval
                # where this one is running can check when it has finished.
                # Otherwise, it could happen that a new scan is initiated before the ones waiting know
                # the previous one has finished, making them stay on the loop unnecessarily.
                self._scan_task = asyncio.create_task(self.wpa.send_command_scan(timeout=15))
                await self._scan_task
                data = await self.wpa.send_command_scan_results()
                networks_list = WifiManager.__dict_from_table(data)
                self._updated_scan_results = [ScannedWifiNetwork(**network) for network in networks_list]
            except Exception as error:
                if self._scan_task is not None:
                    self._scan_task.cancel()
                self._updated_scan_results = None
                raise FetchError("Failed to fetch wifi list.") from error

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

    async def connect_to_network(self, network_id: int) -> None:
        """Connect to wifi network

        Arguments:
            network_id {int} -- Network ID provided by WPA Supplicant
        """
        try:
            await self.wpa.send_command_select_network(network_id)
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
            await self.wpa.send_command_reconnect()
        except Exception as error:
            raise ConnectionError(f"Failed to connect to network. {error}") from error

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
        try:
            await self.wpa.send_command_disconnect()
        except Exception as error:
            raise ConnectionError("Failed to disconnect from wifi network.") from error

    async def enable_saved_networks(self) -> None:
        """Enable saved networks."""
        try:
            saved_networks = await self.get_saved_wifi_network()
            for network in saved_networks:
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
        was_connected = True
        while True:
            await asyncio.sleep(2.5)
            status = await self.status()
            is_connected = "wpa_state" in status and not status["wpa_state"] in ["DISCONNECTED", "SCANNING"]

            if was_connected and not is_connected:
                self.connection_status = ConnectionStatus.JUST_DISCONNECTED
                time_disconnection = time.time()
                was_connected = False
                logger.debug("Lost connection.")
            elif not was_connected and not is_connected:
                self.connection_status = ConnectionStatus.STILL_DISCONNECTED
                seconds_disconnected = time.time() - time_disconnection
                logger.debug(f"Seconds since disconnection: {seconds_disconnected}.")
            elif not was_connected and is_connected:
                self.connection_status = ConnectionStatus.JUST_CONNECTED
                seconds_disconnected = 0
                networks_reenabled = False
                was_connected = True
                logger.debug("Regained connection.")
            else:
                self.connection_status = ConnectionStatus.STILL_CONNECTED

            if not networks_reenabled and seconds_disconnected >= seconds_before_reconnecting:
                await self.enable_saved_networks()
                await self.wpa.send_command_reconnect()
                networks_reenabled = True
                logger.debug("Enabled all networks.")
