import sys
from typing import List, cast

from fastapi import APIRouter, HTTPException, status
from fastapi_versioning import versioned_api_route
from loguru import logger
from typedefs import WifiInterface, WifiInterfaceList
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager

interfaces_router_v2 = APIRouter(
    prefix="/interfaces",
    tags=["interfaces_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def get_wifi_manager() -> AbstractWifiManager:
    main_module = sys.modules.get("main") or sys.modules.get("__main__")
    if main_module is None or not hasattr(main_module, "wifi_manager"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WiFi manager module not found")
    if main_module.wifi_manager is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WiFi manager not initialized")
    return cast(AbstractWifiManager, main_module.wifi_manager)


@interfaces_router_v2.get("/", response_model=WifiInterfaceList, summary="List all WiFi interfaces.")
async def list_interfaces() -> WifiInterfaceList:
    """Get list of all available WiFi interfaces on the system.

    Returns interface name, connection status, connected SSID (if any),
    signal strength, and IP address. Also indicates which interface (if any)
    is currently running the hotspot.
    """
    manager = get_wifi_manager()

    if not hasattr(manager, "get_wifi_interfaces"):
        # Fallback for managers that don't support multi-interface
        try:
            wifi_status = await manager.status()
            interfaces: List[WifiInterface] = [
                WifiInterface(
                    name="wlan0",
                    connected=wifi_status.state == "connected",
                    ssid=wifi_status.ssid,
                    signal_strength=None,
                    ip_address=wifi_status.ip_address,
                    mac_address=None,
                )
            ]
        except Exception as e:
            logger.error(f"Error getting interface status: {e}")
            interfaces = []
        hotspot_interface = "wlan0" if await manager.hotspot_is_running() else None
    else:
        interfaces = await manager.get_wifi_interfaces()
        hotspot_interface = await manager.get_hotspot_interface() if hasattr(manager, "get_hotspot_interface") else None

    return WifiInterfaceList(interfaces=interfaces, hotspot_interface=hotspot_interface)


@interfaces_router_v2.get("/{interface_name}", response_model=WifiInterface, summary="Get specific interface status.")
async def get_interface(interface_name: str) -> WifiInterface:
    """Get detailed status for a specific WiFi interface."""
    manager = get_wifi_manager()

    if not hasattr(manager, "get_interface_status"):
        if interface_name != "wlan0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interface '{interface_name}' not found. Multi-interface support requires NetworkManager.",
            )
        wifi_status = await manager.status()
        return WifiInterface(
            name="wlan0",
            connected=wifi_status.state == "connected",
            ssid=wifi_status.ssid,
            signal_strength=None,
            ip_address=wifi_status.ip_address,
            mac_address=None,
        )

    interface: WifiInterface | None = await manager.get_interface_status(interface_name)
    if interface is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interface '{interface_name}' not found")
    return interface
