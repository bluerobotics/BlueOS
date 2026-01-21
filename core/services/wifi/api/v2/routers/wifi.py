import sys
from typing import List, cast

from fastapi import APIRouter, HTTPException, status
from fastapi_versioning import versioned_api_route
from typedefs import (
    ConnectRequest,
    DisconnectRequest,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiInterfaceScanResult,
    WifiInterfaceStatus,
)
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager

wifi_router_v2 = APIRouter(
    prefix="/wifi",
    tags=["wifi_v2"],
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


@wifi_router_v2.get(
    "/scan/{interface_name}",
    response_model=WifiInterfaceScanResult,
    summary="Scan for networks on a specific interface.",
)
async def scan_interface(interface_name: str) -> WifiInterfaceScanResult:
    """Scan for available WiFi networks using a specific interface.

    Each interface can see different networks depending on its physical location
    and capabilities.
    """
    manager = get_wifi_manager()
    networks: List[ScannedWifiNetwork]

    if hasattr(manager, "scan_interface"):
        networks = await manager.scan_interface(interface_name)
    else:
        if interface_name != "wlan0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interface '{interface_name}' not found. Multi-interface support requires NetworkManager.",
            )
        networks = await manager.get_wifi_available()

    return WifiInterfaceScanResult(interface=interface_name, networks=networks)


@wifi_router_v2.get(
    "/scan",
    response_model=List[WifiInterfaceScanResult],
    summary="Scan for networks on all interfaces.",
)
async def scan_all_interfaces() -> List[WifiInterfaceScanResult]:
    """Scan for available WiFi networks on all interfaces.

    Returns scan results grouped by interface.
    """
    manager = get_wifi_manager()

    if hasattr(manager, "scan_all_interfaces"):
        result: List[WifiInterfaceScanResult] = await manager.scan_all_interfaces()
        return result

    networks = await manager.get_wifi_available()
    return [WifiInterfaceScanResult(interface="wlan0", networks=networks)]


@wifi_router_v2.get(
    "/status/{interface_name}",
    response_model=WifiInterfaceStatus,
    summary="Get connection status for a specific interface.",
)
async def get_status(interface_name: str) -> WifiInterfaceStatus:
    """Get detailed connection status for a specific WiFi interface."""
    manager = get_wifi_manager()

    if hasattr(manager, "get_interface_connection_status"):
        wifi_status: WifiInterfaceStatus = await manager.get_interface_connection_status(interface_name)
        return wifi_status

    if interface_name != "wlan0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface '{interface_name}' not found. Multi-interface support requires NetworkManager.",
        )
    status_data = await manager.status()
    return WifiInterfaceStatus(
        interface="wlan0",
        state=status_data.state or "unknown",
        ssid=status_data.ssid,
        bssid=status_data.bssid,
        ip_address=status_data.ip_address,
        signal_strength=None,
        frequency=int(status_data.freq) if status_data.freq else None,
        key_mgmt=status_data.key_mgmt,
    )


@wifi_router_v2.get(
    "/status",
    response_model=List[WifiInterfaceStatus],
    summary="Get connection status for all interfaces.",
)
async def get_all_status() -> List[WifiInterfaceStatus]:
    """Get connection status for all WiFi interfaces."""
    manager = get_wifi_manager()

    if hasattr(manager, "get_all_interface_status"):
        result: List[WifiInterfaceStatus] = await manager.get_all_interface_status()
        return result

    status_data = await manager.status()
    return [
        WifiInterfaceStatus(
            interface="wlan0",
            state=status_data.state or "unknown",
            ssid=status_data.ssid,
            bssid=status_data.bssid,
            ip_address=status_data.ip_address,
            signal_strength=None,
            frequency=int(status_data.freq) if status_data.freq else None,
            key_mgmt=status_data.key_mgmt,
        )
    ]


@wifi_router_v2.post(
    "/connect",
    summary="Connect to a network on a specific interface.",
)
async def connect(request: ConnectRequest) -> dict[str, str]:
    """Connect to a WiFi network using a specific interface.

    This allows connecting to the same network on multiple interfaces,
    or different networks on different interfaces.

    Note: The hotspot always runs on wlan0 and is managed separately.
    """
    manager = get_wifi_manager()

    try:
        if hasattr(manager, "connect_interface"):
            await manager.connect_interface(request.interface, request.credentials, request.hidden)
        else:
            if request.interface != "wlan0":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Interface '{request.interface}' not supported. Multi-interface support requires NetworkManager.",
                )
            await manager.try_connect_to_network(request.credentials, request.hidden)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    return {"status": "connecting", "interface": request.interface, "ssid": request.credentials.ssid}


@wifi_router_v2.post(
    "/disconnect",
    summary="Disconnect a specific interface.",
)
async def disconnect(request: DisconnectRequest) -> dict[str, str]:
    """Disconnect a specific WiFi interface from its current network."""
    manager = get_wifi_manager()

    if hasattr(manager, "disconnect_interface"):
        await manager.disconnect_interface(request.interface)
    else:
        if request.interface != "wlan0":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Interface '{request.interface}' not supported. Multi-interface support requires NetworkManager.",
            )
        await manager.disconnect()

    return {"status": "disconnected", "interface": request.interface}


@wifi_router_v2.get(
    "/saved",
    response_model=List[SavedWifiNetwork],
    summary="Get all saved WiFi networks.",
)
async def get_saved_networks() -> List[SavedWifiNetwork]:
    """Get list of all saved WiFi networks.

    Saved networks are shared across all interfaces.
    """
    manager = get_wifi_manager()
    result: List[SavedWifiNetwork] = await manager.get_saved_wifi_network()
    return result


@wifi_router_v2.delete(
    "/saved/{ssid}",
    summary="Remove a saved network.",
)
async def remove_saved_network(ssid: str) -> dict[str, str]:
    """Remove a saved WiFi network profile."""
    manager = get_wifi_manager()

    try:
        await manager.remove_network(ssid)
    except StopIteration as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Network '{ssid}' not found in saved networks."
        ) from error

    return {"status": "removed", "ssid": ssid}
