#! /usr/bin/env python3
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from api.dns import DnsData
from api.manager import EthernetManager, NetworkInterface, NetworkInterfaceMetricApi
from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.DHCPServerManager import DHCPServerDetails, DHCPServerLease
from commonwealth.utils.events import events
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from config import SERVICE_NAME
from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from typedefs import Route
from uvicorn import Config, Server

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)
events.publish_start()

manager = EthernetManager()

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
async def configure_interface(interface: NetworkInterface = Body(...)) -> Any:
    """REST API endpoint to configure a new ethernet interface or modify an existing one."""
    await manager.set_configuration(interface)
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


@app.get("/dhcp/details/{interface_name}", summary="Get all DHCP leases.")
@version(1, 0)
def get_dhcp_server_details(interface_name: Optional[str] = None) -> Dict[str, DHCPServerDetails]:
    """REST API endpoint to get the DHCP server details."""
    return manager.get_dhcp_server_details(interface_name)


@app.get("/dhcp/leases/{interface_name}", summary="Get all DHCP leases.")
@version(1, 0)
def get_dhcp_server_leases(interface_name: Optional[str] = None) -> Dict[str, List[DHCPServerLease]]:
    """REST API endpoint to get the DHCP leases."""
    return manager.get_dhcp_server_leases(interface_name)


@app.post("/dhcp", summary="Add local DHCP server to interface.")
@version(1, 0)
async def add_dhcp_server(interface_name: str, ipv4_gateway: str, is_backup_server: bool = False) -> Any:
    """REST API endpoint to enable/disable local DHCP server."""
    manager.add_dhcp_server_to_interface(interface_name, ipv4_gateway, is_backup_server)
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


@app.post("/route", summary="Add route to interface.")
@version(1, 0)
def add_route(interface_name: str, route: Route) -> Any:
    """REST API endpoint to add route."""
    manager.add_route(interface_name, route)
    manager.save()


@app.delete("/route", summary="Remove route from interface.")
@version(1, 0)
def remove_route(interface_name: str, route: Route) -> Any:
    """REST API endpoint remove route."""
    manager.remove_route(interface_name, route)
    manager.save()


@app.get("/route", summary="Get the interface routes.")
@version(1, 0)
def get_route(interface_name: str) -> List[Route]:
    """REST API endpoint to get routes."""
    return list(manager.get_routes(interface_name, ignore_unmanaged=False))


app = VersionedFastAPI(
    app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)


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


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    config = Config(app=app, host="0.0.0.0", port=9090, log_config=None)
    server = Server(config)

    await manager.initialize()
    asyncio.create_task(manager.watchdog())

    # Publish running event when service is ready
    events.publish_running()
    events.publish_health("ready", {"port": 9090})

    await server.serve()


if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error(
            "You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting."
        )
        sys.exit(1)

    asyncio.run(main())
