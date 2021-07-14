#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from typing import Any, List

import uvicorn
from commonwealth.utils.apis import PrettyJSONResponse
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version

from exceptions import BusyError, FetchError
from WifiManager import (
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
    WifiManager,
)

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")


wifi_manager = WifiManager()


app = FastAPI(
    title="WiFi Manager API",
    description="WiFi Manager is responsible for managing WiFi connections on Companion.",
    default_response_class=PrettyJSONResponse,
)


@app.get("/status", summary="Retrieve status of wifi manager.")
@version(1, 0)
def network_status() -> Any:
    try:
        return wifi_manager.status()
    except FetchError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.get("/scan", response_model=List[ScannedWifiNetwork], summary="Retrieve available wifi networks.")
@version(1, 0)
def scan() -> Any:
    try:
        return wifi_manager.get_wifi_available()
    except BusyError as error:
        raise HTTPException(status_code=status.HTTP_425_TOO_EARLY, detail=str(error)) from error
    except FetchError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.get("/saved", response_model=List[SavedWifiNetwork], summary="Retrieve saved wifi networks.")
@version(1, 0)
def saved() -> Any:
    try:
        return wifi_manager.get_saved_wifi_network()
    except FetchError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.post("/connect", summary="Connect to wifi network.")
@version(1, 0)
def connect(credentials: WifiCredentials) -> Any:
    try:
        wifi_manager.set_wifi_password(credentials)
    except ConnectionError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@app.get("/disconnect", summary="Disconnect from wifi network.")
@version(1, 0)
def disconnect() -> Any:
    try:
        wifi_manager.disconnect()
    except ConnectionError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":

    if os.geteuid() != 0:
        print("You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Abstraction CLI for WifiManager configuration.")
    parser.add_argument(
        "--socket",
        dest="socket_name",
        type=str,
        help="Name of the WPA Supplicant socket. Usually 'wlan0' or 'wlp4s0'.",
    )
    args = parser.parse_args()

    wpa_socket_folder = "/var/run/wpa_supplicant/"
    try:
        if args.socket_name:
            socket_name = args.socket_name
        else:
            socket_name = os.listdir(wpa_socket_folder)[0]
        WLAN_SOCKET = os.path.join(wpa_socket_folder, socket_name)
        wifi_manager.connect(WLAN_SOCKET)
    except Exception as socket_connection_error:
        print(socket_connection_error)
        print("Could not connect with provided socket. Connecting via internet socket.")
        try:
            wifi_manager.connect(("127.0.0.1", 6664))
        except Exception as udp_connection_error:
            print(f"Could not connect with internet socket: {udp_connection_error}. Exiting.")
            sys.exit(1)

    uvicorn.run(app, host="0.0.0.0", port=9000)
