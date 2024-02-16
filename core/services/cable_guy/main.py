#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import sys
from typing import Any, List

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

from api.dns import DnsData
from api.manager import (
    AddressMode,
    EthernetManager,
    InterfaceAddress,
    NetworkInterface,
    NetworkInterfaceMetricApi,
)

SERVICE_NAME = "cable-guy"

parser = argparse.ArgumentParser(description="CableGuy service for Blue Robotics BlueOS")
parser.add_argument(
    "--default_config",
    dest="default_config",
    type=str,
    default="bluerov2",
    choices=["bluerov2"],
    help="Specify configuration to use if settings file cannot be loaded or is not found. Defaults to 'bluerov2'.",
)

args = parser.parse_args()

if args.default_config == "bluerov2":
    default_configs = [
        NetworkInterface(name="eth0", addresses=[InterfaceAddress(ip="192.168.2.2", mode=AddressMode.Unmanaged)]),
        NetworkInterface(name="usb0", addresses=[InterfaceAddress(ip="192.168.3.1", mode=AddressMode.Server)]),
    ]

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

manager = EthernetManager(default_configs)

app = FastAPI(
    title="Cable Guy API",
    description="Cable Guy is responsible for managing internet interfaces on BlueOS.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
app.router.route_class = GenericErrorHandlingRoute


@app.get("/ethernet", response_model=List[NetworkInterface], summary="Retrieve ethernet interfaces.")
@version(1, 0)
@temporary_cache(timeout_seconds=10)
def retrieve_ethernet_interfaces() -> Any:
    """REST API endpoint to retrieve the configured ethernet interfaces."""
    return manager.get_ethernet_interfaces()


@app.post("/ethernet", response_model=NetworkInterface, summary="Configure a ethernet interface.")
@version(1, 0)
def configure_interface(interface: NetworkInterface = Body(...)) -> Any:
    """REST API endpoint to configure a new ethernet interface or modify an existing one."""
    manager.set_configuration(interface)
    manager.save()
    return interface


@app.get("/interfaces", response_model=List[NetworkInterface], summary="Retrieve all network interfaces.")
@version(1, 0)
@temporary_cache(timeout_seconds=1)
def retrieve_interfaces() -> Any:
    """REST API endpoint to retrieve the all network interfaces."""
    return manager.get_interfaces()


@app.post("/set_interfaces_priority", summary="Set interface priority")
@version(1, 0)
def set_interfaces_priority(interfaces: List[NetworkInterfaceMetricApi]) -> Any:
    """REST API endpoint to set the interface priority."""
    return manager.set_interfaces_priority(interfaces)


@app.post("/address", summary="Add IP address to interface.")
@version(1, 0)
def add_address(interface_name: str, ip_address: str) -> Any:
    """REST API endpoint to add a static IP address to an ethernet interface."""
    manager.add_static_ip(interface_name, ip_address)
    manager.save()


@app.delete("/address", summary="Delete IP address from interface.")
@version(1, 0)
def delete_address(interface_name: str, ip_address: str) -> Any:
    """REST API endpoint to delete an IP address from an ethernet interface."""
    manager.remove_ip(interface_name, ip_address)
    manager.save()


@app.post("/dhcp", summary="Add local DHCP server to interface.")
@version(1, 0)
def add_dhcp_server(interface_name: str, ipv4_gateway: str) -> Any:
    """REST API endpoint to enable/disable local DHCP server."""
    manager.add_dhcp_server_to_interface(interface_name, ipv4_gateway)
    manager.save()


@app.delete("/dhcp", summary="Remove local DHCP server from interface.")
@version(1, 0)
def remove_dhcp_server(interface_name: str) -> Any:
    """REST API endpoint to enable/disable local DHCP server."""
    manager.remove_dhcp_server_from_interface(interface_name)
    manager.save()


@app.post("/dynamic_ip", summary="Trigger reception of dynamic IP.")
@version(1, 0)
def trigger_dynamic_ip_acquisition(interface_name: str) -> Any:
    """REST API endpoint to trigger interface to receive a new dynamic IP."""
    manager.trigger_dynamic_ip_acquisition(interface_name)
    manager.save()


@app.get("/host_dns", summary="Retrieve host DNS configuration.")
@version(1, 0)
def retrieve_host_dns() -> Any:
    """REST API endpoint to retrieve the host DNS configuration."""
    return manager.dns.retrieve_host_nameservers()


@app.post("/host_dns", summary="Update host DNS configuration.")
@version(1, 0)
def update_host_dns(dns_data: DnsData) -> Any:
    """REST API endpoint to update the host DNS configuration."""
    manager.dns.update_host_nameservers(dns_data)


@app.get("/")
async def root() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>Cable Guy</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


app = VersionedFastAPI(
    app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)

if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error(
            "You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting."
        )
        sys.exit(1)

    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=9090, log_config=None)
    server = Server(config)

    loop.run_until_complete(server.serve())
