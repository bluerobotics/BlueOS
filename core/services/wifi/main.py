#!/usr/bin/env python3

import json
import os
import sys
from typing import Any, List

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi_versioning import VersionedFastAPI, version
from starlette.responses import Response as StarletteResponse

from WifiManager import (
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
    WifiManager,
)

wifi_manager = WifiManager()

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


class PrettyJSONResponse(StarletteResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": "),
        ).encode(self.charset)


app = FastAPI(
    title="WiFi Manager API",
    description="WiFi Manager is responsible for managing WiFi connections on Companion.",
    default_response_class=PrettyJSONResponse,
)


@app.get("/status", summary="Retrieve status of wifi manager.")
@version(1, 0)
def network_status() -> Any:
    return wifi_manager.status()


@app.get("/scan", response_model=List[ScannedWifiNetwork], summary="Retrieve available wifi networks.")
@version(1, 0)
def scan() -> Any:
    try:
        return wifi_manager.get_wifi_available()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.get("/saved", response_model=List[SavedWifiNetwork], summary="Retrieve saved wifi networks.")
@version(1, 0)
def saved() -> Any:
    try:
        return wifi_manager.get_saved_wifi_network()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.post("/connect", summary="Retrieve ethernet interfaces.")
@version(1, 0)
def connect(credentials: WifiCredentials) -> Any:
    wifi_manager.set_wifi_password(credentials)
    return wifi_manager.status()


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting.")
        sys.exit(1)

    WLAN0_SOCKET = "/var/run/wpa_supplicant/wlan0"
    if not os.path.exists(WLAN0_SOCKET):
        print("Connecting via internet socket.")
        wifi_manager.connect(("0.0.0.0", 6664))
    else:
        wifi_manager.connect(WLAN0_SOCKET)

    uvicorn.run(app, host="0.0.0.0", port=9000)
