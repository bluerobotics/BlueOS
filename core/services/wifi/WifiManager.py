from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from wpa_supplicant import WPASupplicant


class ScannedWifiNetwork(BaseModel):
    ssid: str
    bssid: str
    flags: str
    frequency: int
    signallevel: int


class SavedWifiNetwork(BaseModel):
    networkid: int
    ssid: str
    bssid: str
    flags: Optional[str]


class WifiCredentials(BaseModel):
    ssid: str
    password: str


class WifiManager:
    wpa = WPASupplicant()

    def connect(self, path: Any) -> None:
        """Does the connection with wpa_supplicant service

        Arguments:
            path {[tuple/str]} -- Can be a tuple to connect (ip/port) or unix socket file
        """
        self.wpa.run(path)
        # Request scan to update state
        self.wpa.send_command_scan()

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
        temp_header = listed_lines.pop(0)[0]
        header = temp_header.replace(b" ", b"").split(b"/")

        output: List[Any] = []
        for line in listed_lines:
            output += [{}]
            for key, value in zip(header, line):
                output[-1][WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)

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
            key, value = line.split(b"=")
            output[WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)

        return output

    def get_wifi_available(self) -> List[ScannedWifiNetwork]:
        """Get a dict from the wifi signals available"""
        self.wpa.send_command_scan()
        data, result = self.wpa.send_command_scan_results()
        if not result:
            raise ValueError("Failed to fetch wifi list.")

        networks_list = WifiManager.__dict_from_table(data)
        return [ScannedWifiNetwork(**network) for network in networks_list]

    def get_saved_wifi_network(self) -> List[SavedWifiNetwork]:
        """Get a list of saved wifi networks"""
        data, result = self.wpa.send_command_list_networks()
        if not result:
            raise ValueError("Failed to fetch saved wifi list.")

        networks_list = WifiManager.__dict_from_table(data)
        return [SavedWifiNetwork(**network) for network in networks_list]

    def set_wifi_password(self, credentials: WifiCredentials) -> Any:
        """Set network ssid and password

        Arguments:
            credentials {[WifiCredentials]} -- object containing ssid and password of the network
        """
        data, result = self.wpa.send_command_add_network()
        data = data.strip()

        if not result or data == b"Fail":
            return "Failed to add new network"

        network_number = data.decode("utf-8")
        self.wpa.send_command_set_network(network_number, "ssid", '"{}"'.format(credentials.ssid))
        self.wpa.send_command_set_network(network_number, "psk", '"{}"'.format(credentials.password))
        self.wpa.send_command_enable_network(network_number)
        answer, result = self.wpa.send_command_save_config()
        answer = answer.strip()
        if not result or answer == b"FAIL":
            return f"Failed to set network: {str(answer)}"
        self.wpa.send_command_reconfigure()

    def status(self) -> Dict[str, Any]:
        """Check wpa_supplicant status"""
        data, result = self.wpa.send_command_status()
        if not result:
            return {"error": "Failed to get status from network manager"}

        return WifiManager.__dict_from_list(data)

    def reconfigure(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        self.wpa.send_command_reconfigure()
