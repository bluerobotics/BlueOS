#!/usr/bin/env python3

import json
import os
from typing import Any, Dict, List, Union

import bottle
from wpa_supplicant import WPASupplicant


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

    def get_wifi_available(self) -> Union[List[Dict[str, Any]], str]:
        """Get a dict from the wifi signals available"""
        self.wpa.send_command_scan()
        data, result = self.wpa.send_command_scan_results()
        if not result:
            return "Failed to fetch wifi list"

        return WifiManager.__dict_from_table(data)

    def get_saved_wifi_network(self) -> Union[List[Dict[str, Any]], str]:
        """Get a list of saved wifi networks"""
        data, result = self.wpa.send_command_list_networks()
        if not result:
            return "Failed to fetch saved wifi list"

        return WifiManager.__dict_from_table(data)

    def set_wifi_password(self, ssid: str, password: str) -> Any:
        """Set network ssid and password

        Arguments:
            ssid {[str]} -- ssid network name
            password {[str]} -- network password
        """
        data, result = self.wpa.send_command_add_network()
        data = data.strip()

        if not result or data == b"Fail":
            return "Failed to add new network"

        network_number = data.decode("utf-8")
        self.wpa.send_command_set_network(network_number, "ssid", '"{}"'.format(ssid))
        self.wpa.send_command_set_network(network_number, "psk", '"{}"'.format(password))
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


if __name__ == "__main__":
    wifi_manager = WifiManager()
    WLAN0_SOCKET = "/var/run/wpa_supplicant/wlan0"
    REST_API_PREFIX = "/service/network/wifi"
    if not os.path.exists(WLAN0_SOCKET):
        print("Connecting via internet socket.")
        wifi_manager.connect(("0.0.0.0", 6664))
    else:
        wifi_manager.connect(WLAN0_SOCKET)

    def to_pretty_json(data: Any) -> bytes:
        bottle.response.content_type = "application/json; charset=UTF-8"
        return json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False).encode("utf-8")

    @bottle.route(REST_API_PREFIX + "/status")
    def status() -> bytes:
        return to_pretty_json(wifi_manager.status())

    @bottle.route(REST_API_PREFIX + "/scan")
    def scan() -> bytes:
        return to_pretty_json(wifi_manager.get_wifi_available())

    @bottle.route(REST_API_PREFIX + "/saved")
    def saved() -> bytes:
        return to_pretty_json(wifi_manager.get_saved_wifi_network())

    @bottle.post(REST_API_PREFIX + "/connect")
    def connect() -> bytes:
        # curl -H "Content-Type: application/json"
        #   --data '{ "ssid": "Patrick", "password": "Password" }'
        #   --request POST http://0.0.0.0:8080/network/wifi/connect
        data = json.loads(bottle.request.body.read().decode("utf-8"))

        if not "ssid" in data or data["ssid"].strip() == "":
            return "No ssid provided".encode("utf-8")

        ssid = data["ssid"]
        password = data["password"] if "password" in data else ""
        wifi_manager.set_wifi_password(ssid, password)
        return to_pretty_json(wifi_manager.status())

    bottle.run(host="0.0.0.0", port=9000)
