#!/usr/bin/env python3

import json
import os
from typing import Any

import bottle

from WifiManager import WifiManager

BARE_HTML_TEMPLATE = """
<html lang="en">
<head>
  <title>{title}</title>
</head>
<body>
  {body}
</body>
</html>
"""

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

    @bottle.route("/")
    def home() -> str:
        body = r"<br>".join([f'<a href="{route.rule}">{route.rule}</a>' for route in bottle.app().routes])
        page = BARE_HTML_TEMPLATE.format(title="Wifi Manager", body=body)
        return page

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
