#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    StackedHTTPException,
)
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from tabulate import tabulate
from uvicorn import Config, Server

from exceptions import BusyError
from typedefs import (
    HotspotStatus,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
)
from WifiManager import WifiManager

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")
SERVICE_NAME = "wifi-manager"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting Wifi Manager.")
wifi_manager = WifiManager()


app = FastAPI(
    title="WiFi Manager API",
    description="WiFi Manager is responsible for managing WiFi connections on BlueOS.",
    default_response_class=PrettyJSONResponse,
)
app.router.route_class = GenericErrorHandlingRoute


@app.get("/status", summary="Retrieve status of wifi manager.")
@version(1, 0)
async def network_status() -> Any:
    wifi_status = await wifi_manager.status()
    logger.info("Status:")
    for line in tabulate(list(wifi_status.items())).splitlines():
        logger.info(line)
    return wifi_status


@app.get("/scan", response_model=List[ScannedWifiNetwork], summary="Retrieve available wifi networks.")
@version(1, 0)
async def scan() -> Any:
    logger.info("Trying to perform network scan.")
    try:
        available_networks = await wifi_manager.get_wifi_available()
        logger.info("Available networks:")
        for line in tabulate([network.dict() for network in available_networks], headers="keys").splitlines():
            logger.info(line)
        return available_networks
    except BusyError as error:
        raise StackedHTTPException(status_code=status.HTTP_425_TOO_EARLY, error=error) from error


@app.get("/saved", response_model=List[SavedWifiNetwork], summary="Retrieve saved wifi networks.")
@version(1, 0)
async def saved() -> Any:
    logger.info("Trying to fetch saved networks.")
    saved_networks = await wifi_manager.get_saved_wifi_network()
    logger.info("Saved networks:")
    for line in tabulate([network.dict() for network in saved_networks], headers="keys").splitlines():
        logger.info(line)
    return saved_networks


@app.post("/connect", summary="Connect to wifi network.")
@version(1, 0)
async def connect(credentials: WifiCredentials, hidden: bool = False) -> Any:
    logger.info(f"Trying to connect to '{credentials.ssid}' with password '{credentials.password}'.")

    network_id: Optional[int] = None
    is_new_network = False
    try:
        saved_networks = await wifi_manager.get_saved_wifi_network()
        match_network = next(filter(lambda network: network.ssid == credentials.ssid, saved_networks))
        network_id = match_network.networkid
        logger.info(f"Network is already known, id={network_id}.")
    except StopIteration:
        logger.info("Network is not known.")
        is_new_network = True

    is_secure = False
    try:
        available_networks = await wifi_manager.get_wifi_available()
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
            await wifi_manager.remove_network(network_id)
            network_id = await wifi_manager.add_network(credentials, hidden)
            logger.info(f"Network entry updated, id={network_id}.")

        if network_id is None:
            network_id = await wifi_manager.add_network(credentials, hidden)
            logger.info(f"Saving new network entry, id={network_id}.")

        logger.info("Performing network connection.")
        if network_id is None:
            raise ValueError("Missing 'network_id' for network connection.")
        await wifi_manager.connect_to_network(network_id, timeout=40)
    except ConnectionError as error:
        if is_new_network and network_id is not None:
            logger.info("Removing new network entry since connection failed.")
            await wifi_manager.remove_network(network_id)
        raise error
    logger.info(f"Successfully connected to '{credentials.ssid}'.")


@app.post("/remove", summary="Remove saved wifi network.")
@version(1, 0)
async def remove(ssid: str) -> Any:
    logger.info(f"Trying to remove network '{ssid}'.")
    try:
        saved_networks = await wifi_manager.get_saved_wifi_network()
        # Here we get all networks that match the ssid
        # and get a list where the biggest networkid comes first.
        # If we remove the lowest numbers first, it'll change the highest values to -1
        # TODO: We should move the entire wifi framestack to work with bssid
        match_networks = [network for network in saved_networks if network.ssid == ssid]
        match_networks = sorted(match_networks, key=lambda network: network.networkid, reverse=True)
        for match_network in match_networks:
            await wifi_manager.remove_network(match_network.networkid)
    except StopIteration as error:
        logger.info(f"Network '{ssid}' is unknown.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Network '{ssid}' not saved.") from error
    logger.info(f"Successfully removed '{ssid}'.")


@app.get("/disconnect", summary="Disconnect from wifi network.")
@version(1, 0)
async def disconnect() -> Any:
    logger.info("Trying to disconnect from current network.")
    await wifi_manager.disconnect()
    logger.info("Successfully disconnected from network.")


@app.get("/hotspot", summary="Get hotspot state.")
@version(1, 0)
def hotspot_state() -> HotspotStatus:
    return HotspotStatus(supported=wifi_manager.hotspot.supports_hotspot, enabled=wifi_manager.hotspot.is_running())


@app.post("/hotspot", summary="Enable/disable hotspot.")
@version(1, 0)
def toggle_hotspot(enable: bool) -> Any:
    if enable:
        wifi_manager.enable_hotspot()
        return
    wifi_manager.disable_hotspot()


@app.post("/smart_hotspot", summary="Enable/disable smart-hotspot.")
@version(1, 0)
def toggle_smart_hotspot(enable: bool) -> Any:
    if enable:
        wifi_manager.enable_smart_hotspot()
        return
    wifi_manager.disable_smart_hotspot()


@app.post("/hotspot_credentials", summary="Update hotspot credentials.")
@version(1, 0)
def set_hotspot_credentials(credentials: WifiCredentials) -> Any:
    wifi_manager.set_hotspot_credentials(credentials)


@app.get("/hotspot_credentials", summary="Get hotspot credentials.")
@version(1, 0)
def get_hotspot_credentials() -> Any:
    return wifi_manager.hotspot_credentials()


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error("You need root privileges to run this script.\nPlease try again using **sudo**. Exiting.")
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
            logger.info("Connecting via provided socket.")
            socket_name = args.socket_name
        else:
            logger.info("Connecting via default socket.")
            available_sockets = os.listdir(wpa_socket_folder)
            if not available_sockets:
                raise RuntimeError("No wifi sockets available.")
            socket_name = available_sockets[0]
        WLAN_SOCKET = os.path.join(wpa_socket_folder, socket_name)
        wifi_manager.connect(WLAN_SOCKET)
    except Exception as socket_connection_error:
        logger.warning(f"Could not connect with wifi socket. {socket_connection_error}")
        logger.info("Connecting via internet wifi socket.")
        try:
            wifi_manager.connect(("127.0.0.1", 6664))
        except Exception as udp_connection_error:
            logger.error(f"Could not connect with internet socket: {udp_connection_error}. Exiting.")
            sys.exit(1)

    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=9000, log_config=None)
    server = Server(config)

    loop.create_task(wifi_manager.auto_reconnect(60))
    loop.create_task(wifi_manager.start_hotspot_watchdog())
    loop.run_until_complete(server.serve())
