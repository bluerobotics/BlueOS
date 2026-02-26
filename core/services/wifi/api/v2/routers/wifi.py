import sys
from typing import Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException, status
from fastapi_versioning import versioned_api_route
from loguru import logger
from typedefs import (
    ConnectRequest,
    DisconnectRequest,
    HotspotCredentialsRequest,
    HotspotRequest,
    InterfaceHotspotStatus,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    SetInterfaceModeRequest,
    WifiCredentials,
    WifiInterfaceCapabilities,
    WifiInterfaceMode,
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


# Hotspot endpoints


@wifi_router_v2.get(
    "/hotspot/{interface_name}",
    response_model=InterfaceHotspotStatus,
    summary="Get hotspot status for a specific interface.",
)
async def get_hotspot_status(interface_name: str) -> InterfaceHotspotStatus:
    """Get hotspot status for a specific WiFi interface."""
    manager = get_wifi_manager()

    supported = True
    enabled = False
    credentials: Optional[WifiCredentials] = None

    # Check if interface can run a hotspot (either dedicated or dual mode)
    if hasattr(manager, "get_interface_capabilities"):
        caps = await manager.get_interface_capabilities(interface_name)
        supported = caps.supports_ap_mode
    elif hasattr(manager, "supports_hotspot_on_interface"):
        supported = await manager.supports_hotspot_on_interface(interface_name)
    elif hasattr(manager, "supports_hotspot"):
        supported = await manager.supports_hotspot()

    if hasattr(manager, "hotspot_is_running_on_interface"):
        enabled = await manager.hotspot_is_running_on_interface(interface_name)
    elif hasattr(manager, "get_hotspot_interface"):
        # Check if hotspot is running on this specific interface
        current_hotspot_iface = await manager.get_hotspot_interface()
        enabled = current_hotspot_iface == interface_name
    elif hasattr(manager, "hotspot_is_running"):
        # Legacy fallback - can only tell if hotspot is running, not on which interface
        # Assume first interface for backward compatibility
        enabled = await manager.hotspot_is_running() and interface_name == "wlan0"

    # Get per-interface credentials if available
    if hasattr(manager, "hotspot_credentials_for_interface"):
        credentials = manager.hotspot_credentials_for_interface(interface_name)
    elif hasattr(manager, "hotspot_credentials"):
        credentials = manager.hotspot_credentials()

    return InterfaceHotspotStatus(
        interface=interface_name,
        supported=supported,
        enabled=enabled,
        ssid=credentials.ssid if credentials else None,
        password=credentials.password if credentials else None,
    )


@wifi_router_v2.post(
    "/hotspot/enable",
    summary="Enable hotspot on a specific interface.",
)
async def enable_hotspot(request: HotspotRequest) -> Dict[str, str]:
    """Enable hotspot on a specific WiFi interface.

    This allows running a hotspot on any available WiFi interface,
    not just the default one.
    """
    manager = get_wifi_manager()

    try:
        if hasattr(manager, "enable_hotspot_on_interface"):
            success = await manager.enable_hotspot_on_interface(request.interface)
        else:
            success = await manager.enable_hotspot()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enable hotspot on {request.interface}",
            )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    return {"status": "enabled", "interface": request.interface}


@wifi_router_v2.post(
    "/hotspot/disable",
    summary="Disable hotspot on a specific interface.",
)
async def disable_hotspot(request: HotspotRequest) -> Dict[str, str]:
    """Disable hotspot on a specific WiFi interface."""
    manager = get_wifi_manager()

    try:
        if hasattr(manager, "disable_hotspot_on_interface"):
            await manager.disable_hotspot_on_interface(request.interface)
        else:
            await manager.disable_hotspot()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    return {"status": "disabled", "interface": request.interface}


@wifi_router_v2.post(
    "/hotspot/credentials",
    summary="Update hotspot credentials.",
)
async def set_hotspot_credentials(request: HotspotCredentialsRequest) -> Dict[str, str]:
    """Update the hotspot SSID and password for a specific interface.

    If the hotspot is currently running on this interface, it will be restarted
    with the new credentials.
    """
    manager = get_wifi_manager()

    try:
        # Use per-interface method if available
        if hasattr(manager, "set_hotspot_credentials_for_interface"):
            await manager.set_hotspot_credentials_for_interface(request.interface, request.credentials)
        elif hasattr(manager, "set_hotspot_credentials"):
            # Legacy fallback
            await manager.set_hotspot_credentials(request.credentials)
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Hotspot credential management not supported by this handler",
            )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    return {"status": "updated", "interface": request.interface, "ssid": request.credentials.ssid}


# Interface mode endpoints


@wifi_router_v2.get(
    "/mode/{interface_name}",
    response_model=WifiInterfaceCapabilities,
    summary="Get interface capabilities and current mode.",
)
async def get_interface_mode(interface_name: str) -> WifiInterfaceCapabilities:
    """Get the current operating mode and capabilities for an interface.

    Returns information about:
    - Current mode (normal, hotspot, dual)
    - Whether AP mode is supported
    - Whether dual mode (managed + AP simultaneously) is supported
    - Available modes for this interface
    """
    manager = get_wifi_manager()

    if hasattr(manager, "get_interface_capabilities"):
        result: WifiInterfaceCapabilities = await manager.get_interface_capabilities(interface_name)
        return result

    # Fallback for handlers that don't support mode management
    supports_dual = False
    supports_ap = False
    if hasattr(manager, "supports_hotspot_on_interface"):
        supports_dual = await manager.supports_hotspot_on_interface(interface_name)
        supports_ap = supports_dual  # Legacy check only tested dual mode

    available = [WifiInterfaceMode.NORMAL]
    if supports_ap:
        available.append(WifiInterfaceMode.HOTSPOT)
    if supports_dual:
        available.append(WifiInterfaceMode.DUAL)

    return WifiInterfaceCapabilities(
        interface=interface_name,
        supports_ap_mode=supports_ap,
        supports_dual_mode=supports_dual,
        current_mode=WifiInterfaceMode.NORMAL,
        available_modes=available,
    )


@wifi_router_v2.post(
    "/mode",
    summary="Set interface operating mode.",
)
async def set_interface_mode(request: SetInterfaceModeRequest) -> Dict[str, str]:
    """Set the operating mode for a WiFi interface.

    Available modes:
    - **normal**: Client mode only - connect to WiFi networks
    - **hotspot**: AP mode only - interface becomes an access point (disconnects from network)
    - **dual**: Both simultaneously - requires hardware support for interface combinations

    Note: Not all modes are available on all hardware. Check get_interface_mode first.
    """
    manager = get_wifi_manager()

    if not hasattr(manager, "set_interface_mode"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Interface mode management not supported by this handler",
        )

    try:
        success = await manager.set_interface_mode(request.interface, request.mode)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to set mode {request.mode} on {request.interface}",
            )
    except HTTPException as he:
        logger.error(f"HTTPException in set_interface_mode: {he.detail}")
        raise
    except ValueError as e:
        logger.error(f"ValueError in set_interface_mode: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        error_msg = str(e) if str(e) else f"{type(e).__name__}: (no message)"
        logger.error(f"Exception in set_interface_mode: type={type(e).__name__}, msg={error_msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg) from e

    return {"status": "success", "interface": request.interface, "mode": request.mode.value}
