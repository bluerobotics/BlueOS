# pylint: disable=too-many-lines
import asyncio
import hashlib
import re
import select
import signal
import subprocess
from concurrent.futures import CancelledError
from typing import Any, Dict, List, Optional

import sdbus
from commonwealth.utils.general import device_id
from loguru import logger
from sdbus_async.networkmanager import (
    AccessPoint,
    DeviceState,
    DeviceType,
    IPv4Config,
    NetworkConnectionSettings,
    NetworkDeviceWireless,
    NetworkManager,
    NetworkManagerSettings,
)
from sdbus_async.networkmanager.enums import AccessPointCapabilities, WpaSecurityFlags
from typedefs import (
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
    WifiInterface,
    WifiInterfaceCapabilities,
    WifiInterfaceMode,
    WifiInterfaceScanResult,
    WifiInterfaceStatus,
    WifiStatus,
)
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager


class CreateAPException(Exception):
    pass


class InvalidConfigurationError(Exception):
    pass


VIRTUAL_AP_INTERFACE = "uap0"


def get_virtual_ap_name(physical_interface: str) -> str:
    """Generate virtual AP interface name from physical interface name."""
    match = re.search(r"\d+$", physical_interface)
    if match:
        return f"uap{match.group()}"
    return VIRTUAL_AP_INTERFACE


def get_hotspot_gateway(interface: str) -> str:
    """Get unique gateway IP for each interface to avoid conflicts.

    wlan0 → 192.168.42.1
    wlan1 → 192.168.43.1
    wlan2 → 192.168.44.1
    etc.
    """
    match = re.search(r"\d+$", interface)
    if match:
        interface_num = int(match.group())
        return f"192.168.{42 + interface_num}.1"
    return "192.168.42.1"


# pylint: disable=too-many-instance-attributes
class NetworkManagerWifi(AbstractWifiManager):
    """NetworkManager implementation of the WiFi manager interface.

    This class provides WiFi management functionality using NetworkManager and supports
    both client and access point (hotspot) modes across multiple WiFi interfaces.
    """

    def __init__(self) -> None:
        """Initialize NetworkManager WiFi handler."""
        super().__init__()
        self._bus = sdbus.sd_bus_open_system()
        self._nm: Optional[NetworkManager] = None
        self._nm_settings: Optional[NetworkManagerSettings] = None
        self._device_paths: Dict[str, str] = {}
        self._device_path: Optional[str] = None  # For backward compatibility
        self._create_ap_processes: Dict[str, subprocess.Popen[str]] = {}
        self._create_ap_process: Optional[subprocess.Popen[str]] = None  # For backward compatibility
        self._ap_interface = VIRTUAL_AP_INTERFACE
        self._hotspot_interface: Optional[str] = None
        self._interface_modes: Dict[str, WifiInterfaceMode] = {}
        self._interface_capabilities: Dict[str, bool] = {}
        self._tasks: List[asyncio.Task[Any]] = []
        self._nm = NetworkManager(self._bus)
        self._nm_settings = NetworkManagerSettings(self._bus)
        logger.info("NetworkManagerWifi initialized")

    def _save_interface_mode(self, interface: str, mode: WifiInterfaceMode) -> None:
        """Persist the interface mode to settings."""
        interface_modes = self._settings_manager.settings.get_interface_modes()
        interface_modes[interface] = mode.value
        self._settings_manager.settings.set_interface_modes(interface_modes)
        self._settings_manager.save()
        logger.info(f"Saved {interface} mode: {mode.value}")

    def _get_stored_interface_mode(self, interface: str) -> Optional[WifiInterfaceMode]:
        """Get the stored mode for an interface from settings, or None if not set."""
        interface_modes = self._settings_manager.settings.get_interface_modes()
        mode_str = interface_modes.get(interface)
        if mode_str:
            try:
                return WifiInterfaceMode(mode_str)
            except ValueError:
                logger.warning(f"Invalid stored mode '{mode_str}' for {interface}")
        return None

    async def get_default_mode_for_interface(self, interface: str) -> WifiInterfaceMode:
        """Get the default mode for an interface based on stored setting or capabilities."""
        caps = await self.get_interface_capabilities(interface)

        # First check if user has explicitly set a mode
        stored_mode = self._get_stored_interface_mode(interface)
        if stored_mode is not None:
            # Verify the stored mode is still supported by this hardware
            if stored_mode in caps.available_modes:
                return stored_mode
            logger.warning(f"Stored mode {stored_mode} no longer supported on {interface}, using default")

        # No stored preference or stored mode not supported - determine based on capabilities
        if caps.supports_dual_mode:
            return WifiInterfaceMode.DUAL
        return WifiInterfaceMode.NORMAL

    async def restore_interface_modes(self) -> None:
        """Restore interface modes from settings on startup."""
        for interface in list(self._device_paths.keys()):
            try:
                default_mode = await self.get_default_mode_for_interface(interface)
                current_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)
                if default_mode != current_mode:
                    logger.info(f"Restoring {interface} to {default_mode} mode")
                    success = await self.set_interface_mode(interface, default_mode)
                    if not success:
                        logger.warning(f"Failed to restore {interface} to {default_mode} mode, defaulting to NORMAL")
                        self._interface_modes[interface] = WifiInterfaceMode.NORMAL
                else:
                    self._interface_modes[interface] = default_mode
            except Exception as e:
                logger.error(f"Error restoring mode for {interface}: {e}")
                self._interface_modes[interface] = WifiInterfaceMode.NORMAL

    async def _set_interface_managed(self, interface: str, managed: bool) -> None:
        """Set the NetworkManager 'Managed' property for an interface via D-Bus."""
        device_path = self._device_paths.get(interface)
        if not device_path:
            if managed:
                # Try to refresh device paths when restoring management
                await self._refresh_device_paths()
                device_path = self._device_paths.get(interface)
            if not device_path:
                logger.warning(f"Interface {interface} not found, cannot set managed={managed}")
                return

        try:
            msg = self._bus.new_method_call_message(
                "org.freedesktop.NetworkManager",
                device_path,
                "org.freedesktop.DBus.Properties",
                "Set",
            )
            msg.append_data("ssv", "org.freedesktop.NetworkManager.Device", "Managed", ("b", managed))
            await self._bus.call_async(msg)
            logger.info(f"Set {interface} managed={managed} via D-Bus")

            if not managed:
                # NetworkManager will remove the device from its D-Bus tree, so clear cached path
                if interface in self._device_paths:
                    del self._device_paths[interface]
                    logger.debug(f"Removed {interface} from device paths cache (now unmanaged)")
            else:
                # NetworkManager needs time to create the new device object
                # Retry refresh until the device appears or timeout
                for _ in range(10):
                    await asyncio.sleep(0.5)
                    await self._refresh_device_paths()
                    if interface in self._device_paths:
                        break
                else:
                    logger.warning(f"Device {interface} did not appear after setting managed=True")
        except Exception as e:
            logger.error(f"Failed to set {interface} managed={managed}: {e}")

    async def _refresh_device_paths(self) -> None:
        """Refresh the cached device paths from NetworkManager."""
        new_devices = await self._get_wifi_devices()
        self._device_paths.update(new_devices)
        logger.debug(f"Refreshed device paths: {list(self._device_paths.keys())}")

    async def _get_wifi_devices(self) -> Dict[str, str]:
        """Get all WiFi devices, filtering out virtual AP interface."""
        assert self._nm is not None
        devices: Dict[str, str] = {}
        device_paths = await self._nm.get_devices()

        for device_path in device_paths:
            try:
                device = NetworkDeviceWireless(device_path, self._bus)
                if await device.device_type == DeviceType.WIFI:
                    interface_name = await device.interface
                    # Filter out virtual AP interfaces (uap0, uap1, etc.)
                    if not interface_name.startswith("uap"):
                        devices[interface_name] = device_path
            except Exception as e:
                logger.debug(f"Error checking device {device_path}: {e}")
                continue

        return devices

    async def _create_virtual_interface_for(self, physical_interface: str) -> Optional[str]:
        """Create virtual AP interface for a specific physical interface."""
        virtual_ap_name = get_virtual_ap_name(physical_interface)

        try:
            # Check if interface already exists
            existing = subprocess.run(["ip", "link", "show", virtual_ap_name], capture_output=True, check=False)
            if existing.returncode == 0:
                logger.info(f"Interface {virtual_ap_name} already exists")
                return virtual_ap_name

            device_path = self._device_paths.get(physical_interface)
            if not device_path:
                logger.error(f"Physical interface {physical_interface} not found")
                return None

            device = NetworkDeviceWireless(device_path, self._bus)
            phys_name = await device.interface

            # Create virtual interface
            subprocess.run(["iw", "dev", phys_name, "interface", "add", virtual_ap_name, "type", "__ap"], check=True)
            logger.info(f"Created virtual AP interface {virtual_ap_name} from {phys_name}")

            # Set interface up
            subprocess.run(["ip", "link", "set", virtual_ap_name, "up"], check=True)

            # Disable power save on both interfaces
            subprocess.run(["iw", phys_name, "set", "power_save", "off"], check=True)
            subprocess.run(["iw", virtual_ap_name, "set", "power_save", "off"], check=True)

            return virtual_ap_name

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create virtual interface for {physical_interface}: {e}")
            return None

    async def _create_virtual_interface(self) -> bool:
        """Create virtual AP interface using iw (backward compatible - uses first available interface)."""
        # Use first available interface for backward compatibility
        if not self._device_paths:
            logger.error("No WiFi device available for hotspot")
            return False

        physical_interface = next(iter(self._device_paths.keys()))
        result = await self._create_virtual_interface_for(physical_interface)
        if result:
            self._ap_interface = result
            return True
        return False

    async def _cleanup_virtual_interface_for(self, virtual_ap_name: str) -> None:
        """Remove a specific virtual AP interface."""
        try:
            existing = subprocess.run(["ip", "link", "show", virtual_ap_name], capture_output=True, check=False)
            if existing.returncode != 0:
                return

            subprocess.run(["iw", "dev", virtual_ap_name, "del"], check=True)
            logger.info(f"Removed virtual AP interface {virtual_ap_name}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove virtual interface {virtual_ap_name}: {e}")

    async def _cleanup_virtual_interface(self) -> None:
        """Remove virtual AP interface (backward compatible)."""
        await self._cleanup_virtual_interface_for(self._ap_interface)

    async def start(self) -> None:
        """Start NetworkManagerWifi with signal handlers"""
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.handle_shutdown(s)))

        # Find all WiFi devices
        self._device_paths = await self._get_wifi_devices()
        logger.info(f"Found WiFi devices: {list(self._device_paths.keys())}")

        # Set primary device for backward compatibility
        if self._device_paths:
            # Prefer wlan0 if available, otherwise use first device
            if "wlan0" in self._device_paths:
                self._device_path = self._device_paths["wlan0"]
            else:
                self._device_path = next(iter(self._device_paths.values()))

        # Create virtual AP interface if needed
        await self._create_virtual_interface()

        # Restore interface modes from settings
        await self.restore_interface_modes()

        self._tasks.append(asyncio.get_event_loop().create_task(self._autoscan()))
        self._tasks.append(asyncio.get_event_loop().create_task(self.hotspot_watchdog()))

    async def _autoscan(self) -> None:
        """Periodically scan for networks on all interfaces."""
        while True:
            for interface_name, device_path in list(self._device_paths.items()):
                try:
                    device = NetworkDeviceWireless(device_path, self._bus)
                    if await device.last_scan > 10000:
                        await device.request_scan({})
                        logger.debug(f"Requested WiFi scan on {interface_name}")
                except Exception as e:
                    logger.debug(f"Scan request failed on {interface_name}: {e}")
            await asyncio.sleep(10)

    # Multi-interface API methods

    # pylint: disable=too-many-locals,too-many-nested-blocks
    async def get_wifi_interfaces(self) -> List[WifiInterface]:
        """Get list of all WiFi interfaces with their status."""
        interfaces: List[WifiInterface] = []
        processed_interfaces: set[str] = set()

        for interface_name, device_path in list(self._device_paths.items()):
            processed_interfaces.add(interface_name)
            try:
                device = NetworkDeviceWireless(device_path, self._bus)
                state = await device.state
                connected = state == DeviceState.ACTIVATED

                ssid = None
                signal_strength = None
                ip_address = None
                mac_address = None

                try:
                    mac_address = await device.hw_address
                except Exception:
                    pass

                if connected:
                    try:
                        ap = AccessPoint(await device.active_access_point, self._bus)
                        ssid_bytes: bytes = await ap.ssid
                        ssid = ssid_bytes.decode("utf-8")
                        signal_strength = await ap.strength
                    except Exception:
                        pass

                    try:
                        ip4_conf_path = await device.ip4_config
                        if ip4_conf_path and ip4_conf_path != "/":
                            ip4_conf = IPv4Config(ip4_conf_path, self._bus)
                            address_data = await ip4_conf.address_data
                            if address_data:
                                ip_address = address_data[0]["address"][1]
                    except Exception:
                        pass

                # Get mode and capability info
                current_mode = self._interface_modes.get(interface_name, WifiInterfaceMode.NORMAL)
                supports_ap = await self._check_interface_supports_ap_mode(interface_name)
                supports_dual = await self._check_interface_supports_dual_mode(interface_name)

                interfaces.append(
                    WifiInterface(
                        name=interface_name,
                        connected=connected,
                        ssid=ssid,
                        signal_strength=signal_strength,
                        ip_address=ip_address,
                        mac_address=mac_address,
                        mode=current_mode,
                        supports_hotspot=supports_ap,
                        supports_dual_mode=supports_dual,
                    )
                )
            except Exception as e:
                logger.error(f"Error getting status for {interface_name}: {e}")

        # Include interfaces running in direct hotspot mode (unmanaged by NetworkManager)
        for interface_name, process in self._create_ap_processes.items():
            if interface_name not in processed_interfaces and process.poll() is None:
                current_mode = self._interface_modes.get(interface_name, WifiInterfaceMode.HOTSPOT)
                interfaces.append(
                    WifiInterface(
                        name=interface_name,
                        connected=False,  # Not connected to a network, it IS the network
                        ssid=None,
                        signal_strength=None,
                        ip_address=get_hotspot_gateway(interface_name),
                        mac_address=None,
                        mode=current_mode,
                        supports_hotspot=True,
                        supports_dual_mode=False,
                    )
                )

        return interfaces

    # pylint: disable=too-many-locals
    async def get_interface_status(self, interface_name: str) -> Optional[WifiInterface]:
        """Get status for a specific interface."""
        device_path = self._device_paths.get(interface_name)

        # Check if interface is in direct hotspot mode (unmanaged by NetworkManager)
        if not device_path:
            if interface_name in self._create_ap_processes:
                process = self._create_ap_processes[interface_name]
                if process.poll() is None:
                    current_mode = self._interface_modes.get(interface_name, WifiInterfaceMode.HOTSPOT)
                    return WifiInterface(
                        name=interface_name,
                        connected=False,
                        ssid=None,
                        signal_strength=None,
                        ip_address=get_hotspot_gateway(interface_name),
                        mac_address=None,
                        mode=current_mode,
                        supports_hotspot=True,
                        supports_dual_mode=False,
                    )
            return None

        try:
            device = NetworkDeviceWireless(device_path, self._bus)
            state = await device.state
            connected = state == DeviceState.ACTIVATED

            ssid = None
            signal_strength = None
            ip_address = None
            mac_address = None

            try:
                mac_address = await device.hw_address
            except Exception:
                pass

            if connected:
                try:
                    ap = AccessPoint(await device.active_access_point, self._bus)
                    ssid_bytes: bytes = await ap.ssid
                    ssid = ssid_bytes.decode("utf-8")
                    signal_strength = await ap.strength
                except Exception:
                    pass

                try:
                    ip4_conf_path = await device.ip4_config
                    if ip4_conf_path and ip4_conf_path != "/":
                        ip4_conf = IPv4Config(ip4_conf_path, self._bus)
                        address_data = await ip4_conf.address_data
                        if address_data:
                            ip_address = address_data[0]["address"][1]
                except Exception:
                    pass

            # Get mode and capability info
            current_mode = self._interface_modes.get(interface_name, WifiInterfaceMode.NORMAL)
            supports_ap = await self._check_interface_supports_ap_mode(interface_name)
            supports_dual = await self._check_interface_supports_dual_mode(interface_name)

            return WifiInterface(
                name=interface_name,
                connected=connected,
                ssid=ssid,
                signal_strength=signal_strength,
                ip_address=ip_address,
                mac_address=mac_address,
                mode=current_mode,
                supports_hotspot=supports_ap,
                supports_dual_mode=supports_dual,
            )
        except Exception as e:
            logger.error(f"Error getting status for {interface_name}: {e}")
            return None

    async def scan_interface(self, interface_name: str) -> List[ScannedWifiNetwork]:
        """Scan for networks on a specific interface."""
        device_path = self._device_paths.get(interface_name)
        if not device_path:
            raise ValueError(f"Interface '{interface_name}' not found")

        return await self._scan_device(device_path)

    async def scan_all_interfaces(self) -> List[WifiInterfaceScanResult]:
        """Scan for networks on all interfaces."""
        results: List[WifiInterfaceScanResult] = []

        for interface_name, device_path in list(self._device_paths.items()):
            try:
                networks = await self._scan_device(device_path)
                results.append(WifiInterfaceScanResult(interface=interface_name, networks=networks))
            except Exception as e:
                logger.error(f"Error scanning {interface_name}: {e}")
                results.append(WifiInterfaceScanResult(interface=interface_name, networks=[]))

        return results

    # pylint: disable=too-many-locals
    async def _scan_device(self, device_path: str) -> List[ScannedWifiNetwork]:
        """Internal method to scan a specific device."""
        try:
            device = NetworkDeviceWireless(device_path, bus=self._bus)
            networks: List[ScannedWifiNetwork] = []

            ap_paths = await device.get_all_access_points()
            for ap_path in ap_paths:
                ap = AccessPoint(ap_path, self._bus)
                freq = await ap.frequency.get_async()
                ssid = (await ap.ssid.get_async()).decode("utf-8")

                # Get raw flag values
                wpa_flags = await ap.wpa_flags.get_async()
                rsn_flags = await ap.rsn_flags.get_async()
                flags = await ap.flags.get_async()

                security_flags = []

                # Check flag bits
                if flags & AccessPointCapabilities.PRIVACY:
                    security_flags.append("WEP")

                if wpa_flags:
                    if wpa_flags & WpaSecurityFlags.AUTH_PSK:
                        security_flags.append("WPA-PSK")
                    if wpa_flags & WpaSecurityFlags.BROADCAST_TKIP:
                        security_flags.append("TKIP")
                    if wpa_flags & WpaSecurityFlags.BROADCAST_CCMP:
                        security_flags.append("CCMP")

                if rsn_flags:
                    if rsn_flags & WpaSecurityFlags.AUTH_PSK:
                        security_flags.append("WPA2-PSK")
                    if rsn_flags & WpaSecurityFlags.BROADCAST_TKIP:
                        security_flags.append("TKIP")
                    if rsn_flags & WpaSecurityFlags.BROADCAST_CCMP:
                        security_flags.append("CCMP")

                flag_str = f"[{'-'.join(set(security_flags))}]" if security_flags else ""

                strength = await ap.strength.get_async()
                networks.append(
                    ScannedWifiNetwork(
                        ssid=ssid,
                        frequency=freq,
                        bssid=(await ap.hw_address.get_async()),
                        flags=flag_str,
                        signallevel=strength,
                    )
                )

            return networks

        except Exception as e:
            logger.error(f"Error scanning device: {e}")
            return []

    async def get_interface_connection_status(self, interface_name: str) -> WifiInterfaceStatus:
        """Get detailed connection status for a specific interface."""
        device_path = self._device_paths.get(interface_name)
        if not device_path:
            raise ValueError(f"Interface '{interface_name}' not found")

        device = NetworkDeviceWireless(device_path, self._bus)
        state = await device.state

        if state == DeviceState.ACTIVATED:
            try:
                ap_path = await device.active_access_point
                if not ap_path or ap_path == "/":
                    logger.warning(f"No active access point for {interface_name} despite ACTIVATED state")
                    return WifiInterfaceStatus(
                        interface=interface_name,
                        state="connecting",
                        ssid=None,
                        bssid=None,
                        ip_address=None,
                        signal_strength=None,
                        frequency=None,
                        key_mgmt=None,
                    )
                ap = AccessPoint(ap_path, self._bus)
                ssid_bytes: bytes = await ap.ssid
                ip4_conf_path = await device.ip4_config
                ip_address = None

                if ip4_conf_path and ip4_conf_path != "/":
                    ip4_conf = IPv4Config(ip4_conf_path, self._bus)
                    address_data = await ip4_conf.address_data
                    if address_data:
                        ip_address = address_data[0]["address"][1]

                return WifiInterfaceStatus(
                    interface=interface_name,
                    state="connected",
                    ssid=ssid_bytes.decode("utf-8"),
                    bssid=await ap.hw_address,
                    ip_address=ip_address,
                    signal_strength=await ap.strength,
                    frequency=await ap.frequency,
                    key_mgmt="WPA-PSK",
                )
            except Exception as e:
                logger.error(f"Error getting connection status for {interface_name}: {e}")

        return WifiInterfaceStatus(
            interface=interface_name,
            state="disconnected",
            ssid=None,
            bssid=None,
            ip_address=None,
            signal_strength=None,
            frequency=None,
            key_mgmt=None,
        )

    async def get_all_interface_status(self) -> List[WifiInterfaceStatus]:
        """Get connection status for all interfaces."""
        results: List[WifiInterfaceStatus] = []

        for interface_name in list(self._device_paths.keys()):
            try:
                status = await self.get_interface_connection_status(interface_name)
                results.append(status)
            except Exception as e:
                logger.error(f"Error getting status for {interface_name}: {e}")
                results.append(
                    WifiInterfaceStatus(
                        interface=interface_name,
                        state="error",
                        ssid=None,
                        bssid=None,
                        ip_address=None,
                        signal_strength=None,
                        frequency=None,
                        key_mgmt=None,
                    )
                )

        return results

    async def connect_interface(self, interface_name: str, credentials: WifiCredentials, hidden: bool = False) -> None:
        """Connect a specific interface to a network."""
        device_path = self._device_paths.get(interface_name)
        if not device_path:
            raise ValueError(f"Interface '{interface_name}' not found")

        assert self._nm is not None
        assert self._nm_settings is not None

        async def wait_for_connection(timeout: int = 30) -> bool:
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < timeout:
                status = await self.get_interface_connection_status(interface_name)
                if status.state == "connected":
                    return True
                await asyncio.sleep(1)
            return False

        existing_connection = await self._find_existing_connection(credentials)
        if existing_connection:
            logger.info(f"Using existing connection for {credentials.ssid} on {interface_name}")
            await self._nm.activate_connection(existing_connection, device_path, "/")

            # If hotspot was running, restart it
            if not await wait_for_connection():
                logger.error(f"Connection timeout for {credentials.ssid} on {interface_name}")
                raise TimeoutError(f"Failed to connect to {credentials.ssid} on {interface_name} within 30 seconds")

            if self._settings_manager.settings.hotspot_enabled and not await self.hotspot_is_running():
                await self.enable_hotspot()
            return

        # Create connection without interface-name to allow use on any interface
        connection: dict[str, dict[str, tuple[str, Any]]] = {
            "connection": {
                "type": ("s", "802-11-wireless"),
                "id": ("s", credentials.ssid),
                "autoconnect": ("b", True),
            },
            "802-11-wireless": {
                "ssid": ("ay", credentials.ssid.encode()),
                "mode": ("s", "infrastructure"),
                "hidden": ("b", hidden),
            },
            "ipv6": {"method": ("s", "disabled")},
        }

        if credentials.password:
            connection["802-11-wireless-security"] = {"key-mgmt": ("s", "wpa-psk"), "psk": ("s", credentials.password)}
            connection["802-11-wireless"]["security"] = ("s", "802-11-wireless-security")

        # Add and activate connection
        conn_path = await self._nm_settings.add_connection(connection)
        await self._nm.activate_connection(conn_path, device_path, "/")

        if not await wait_for_connection():
            logger.error(f"Connection timeout for {credentials.ssid} on {interface_name}")
            await self.remove_network(credentials.ssid)
            raise TimeoutError(f"Failed to connect to {credentials.ssid} on {interface_name} within 30 seconds")

        if self._settings_manager.settings.hotspot_enabled:
            await self.enable_hotspot()

    async def disconnect_interface(self, interface_name: str) -> None:
        """Disconnect a specific interface."""
        device_path = self._device_paths.get(interface_name)
        if not device_path:
            raise ValueError(f"Interface '{interface_name}' not found")

        assert self._nm is not None
        try:
            device = NetworkDeviceWireless(device_path, self._bus)
            active_connection = await device.active_connection
            if active_connection:
                await self._nm.deactivate_connection(active_connection)
                logger.info(f"Successfully disconnected {interface_name} from network")
            else:
                logger.info(f"No active connection on {interface_name} to disconnect from")
        except Exception as e:
            logger.error(f"Failed to disconnect {interface_name}: {e}")
            raise

    # Original API methods for backward compatibility

    async def get_wifi_available(self) -> List[ScannedWifiNetwork]:
        """Get available networks from the primary device (backward compatible)."""
        if not self._device_path:
            return []
        return await self._scan_device(self._device_path)

    async def try_connect_to_network(self, credentials: WifiCredentials, hidden: bool = False) -> None:
        """Connect using primary interface (backward compatible)."""
        # Find the interface name for the primary device
        primary_interface = None
        for name, path in list(self._device_paths.items()):
            if path == self._device_path:
                primary_interface = name
                break

        if not primary_interface:
            primary_interface = "wlan0"

        await self.connect_interface(primary_interface, credentials, hidden)

    async def _find_existing_connection(self, credentials: WifiCredentials) -> Optional[str]:
        """Find existing connection for given SSID, checking password if provided"""
        try:
            if not self._nm_settings:
                return None

            for conn_path in await self._nm_settings.connections:
                try:
                    settings = NetworkConnectionSettings(conn_path, self._bus)
                    profile = await settings.get_profile()

                    if not profile.wireless or not profile.wireless.ssid:
                        continue

                    if profile.wireless.ssid.decode("utf-8") != credentials.ssid:
                        continue

                    # If no password provided, we can use any existing connection
                    if not credentials.password:
                        logger.info(f"Found existing connection for {credentials.ssid} (no password check)")
                        return str(conn_path)

                    # If password provided, check if it matches
                    if profile.wireless_security and profile.wireless_security.psk == credentials.password:
                        logger.info(f"Found existing connection for {credentials.ssid} with matching password")
                        return str(conn_path)

                    logger.debug(f"Found connection for {credentials.ssid} but password doesn't match")

                except Exception as e:
                    logger.error(f"Error checking connection {conn_path}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error finding existing connection: {e}")
            return None

    # pylint: disable=too-many-branches,too-many-statements
    async def enable_hotspot_on_interface(self, interface: str, save_settings: bool = True) -> bool:
        """Enable hotspot on a specific interface."""
        virtual_ap_name = await self._create_virtual_interface_for(interface)
        if not virtual_ap_name:
            logger.error(f"Failed to create virtual interface for {interface}")
            return False

        credentials = self.hotspot_credentials_for_interface(interface)
        gateway = get_hotspot_gateway(interface)

        cmd = [
            "create_ap",
            "-n",
            virtual_ap_name,
            "-g",
            gateway,
            "--redirect-to-localhost",  # Redirect all traffic to localhost, captive-portal style
            credentials.ssid,
            credentials.password,
        ]

        try:
            # Stop existing hotspot on this interface if running
            if interface in self._create_ap_processes:
                existing_process = self._create_ap_processes[interface]
                if existing_process.poll() is None:
                    logger.info(f"Stopping existing hotspot on {interface}...")
                    existing_process.terminate()
                    existing_process.wait()
                del self._create_ap_processes[interface]

            # pylint: disable=consider-using-with
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1
            )
            # pylint: enable=consider-using-with

            # Wait for "Done" or "ERROR" in output
            success = False
            start_time = asyncio.get_event_loop().time()
            timeout = 30  # 30 second timeout
            while True:
                if process.stdout is not None:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break

                    line = line.strip()
                    if line:
                        logger.info(f"create_ap ({interface}): {line}")
                        if "Done" in line or "AP-ENABLED" in line:
                            success = True
                            break
                        if "ERROR" in line:
                            logger.error(f"create_ap error on {interface}: {line}")
                            raise CreateAPException(f"Failed to start create_ap on {interface}: {line}")

                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        logger.error(f"Timeout waiting for create_ap on {interface}")
                        return success

                    # Give other tasks a chance to run
                    await asyncio.sleep(0.1)

            if not success:
                logger.error(f"Failed to start create_ap on {interface}")
                return success

            logger.info(f"Successfully started create_ap on {interface} with PID {process.pid}")
            self._create_ap_processes[interface] = process
            self._hotspot_interface = interface
            # For backward compatibility
            self._create_ap_process = process
            self._ap_interface = virtual_ap_name

            self._tasks.append(asyncio.get_event_loop().create_task(self._monitor_create_ap_output(process, interface)))

            if save_settings:
                self._settings_manager.settings.hotspot_enabled = True
                self._settings_manager.save()
            logger.info(f"Hotspot enabled on {interface}")

        except CreateAPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error starting create_ap on {interface}: {e}")
        return success

    async def enable_hotspot(self, save_settings: bool = True) -> bool:
        """Enable hotspot (backward compatible - uses first available interface)."""
        if not self._device_paths:
            logger.error("No WiFi device available for hotspot")
            return False

        interface = next(iter(self._device_paths.keys()))
        return await self.enable_hotspot_on_interface(interface, save_settings)

    async def _monitor_create_ap_output(self, process: subprocess.Popen[str], interface: Optional[str] = None) -> None:
        """Monitor create_ap process output non-blockingly using select.

        Also monitors for INTERFACE-DISABLED events and attempts auto-recovery for unstable drivers.
        """
        interface_disabled_time: Optional[float] = None
        recovery_timeout = 10.0  # seconds to wait for auto-recovery before restarting

        try:
            while True:
                if select.select([process.stdout], [], [], 0)[0]:
                    assert process.stdout is not None
                    if line := process.stdout.readline().strip():
                        logger.info(f"create_ap: {line}")

                        # Monitor for interface stability issues (common with RTL8192EU driver)
                        if "INTERFACE-DISABLED" in line:
                            interface_disabled_time = asyncio.get_running_loop().time()
                            logger.warning(f"Hotspot interface {interface} disabled - monitoring for recovery")
                        elif "INTERFACE-ENABLED" in line or "AP-ENABLED" in line:
                            if interface_disabled_time is not None:
                                recovery_time = asyncio.get_running_loop().time() - interface_disabled_time
                                logger.info(f"Hotspot interface {interface} recovered after {recovery_time:.1f}s")
                            interface_disabled_time = None

                # Check if interface has been disabled too long (driver stuck)
                if interface_disabled_time is not None:
                    elapsed = asyncio.get_running_loop().time() - interface_disabled_time
                    if elapsed > recovery_timeout:
                        logger.error(f"Hotspot on {interface} failed to recover after {elapsed:.1f}s - will restart")
                        # Kill the stuck process and let cleanup happen
                        process.terminate()
                        break

                if process.poll() is not None:
                    break

                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error monitoring create_ap output: {e}")
        finally:
            exit_code = process.poll()
            logger.info(f"create_ap process monitoring ended (exit code: {exit_code})")
            if process == self._create_ap_process:
                self._create_ap_process = None
            # Clean up multi-interface tracking
            if interface and interface in self._create_ap_processes:
                if self._create_ap_processes[interface] == process:
                    del self._create_ap_processes[interface]
                    logger.info(f"Removed {interface} from hotspot processes (process exited)")

                    # Check if we should auto-restart the hotspot (if mode is still HOTSPOT)
                    current_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)
                    if current_mode == WifiInterfaceMode.HOTSPOT:
                        # Don't restore to managed - restart will handle it
                        logger.info(f"Auto-restarting hotspot on {interface} (mode is still HOTSPOT)")
                        asyncio.create_task(self._restart_hotspot_after_failure(interface))
                    else:
                        # Restore interface to NetworkManager management
                        asyncio.create_task(self._set_interface_managed(interface, True))
                        # Update mode to NORMAL since hotspot stopped and we're not in hotspot mode
                        self._interface_modes[interface] = WifiInterfaceMode.NORMAL
                        self._save_interface_mode(interface, WifiInterfaceMode.NORMAL)

    async def _restart_hotspot_after_failure(self, interface: str) -> None:
        """Restart hotspot after a failure with exponential backoff."""
        # Wait a bit before restarting to avoid rapid restart loops
        await asyncio.sleep(5.0)

        # Only restart if we're still supposed to be in hotspot mode
        if self._interface_modes.get(interface) != WifiInterfaceMode.HOTSPOT:
            logger.info(f"Not restarting hotspot on {interface} - mode changed")
            # Restore NetworkManager management since we're not restarting
            await self._set_interface_managed(interface, True)
            return

        logger.info(f"Attempting to restart hotspot on {interface}...")
        try:
            success = await self._enable_hotspot_direct(interface)
            if success:
                logger.info(f"Successfully restarted hotspot on {interface}")
            else:
                logger.error(f"Failed to restart hotspot on {interface}")
                # Revert to NORMAL mode and restore NetworkManager management
                self._interface_modes[interface] = WifiInterfaceMode.NORMAL
                self._save_interface_mode(interface, WifiInterfaceMode.NORMAL)
                await self._set_interface_managed(interface, True)
        except Exception as e:
            logger.error(f"Exception restarting hotspot on {interface}: {e}")
            self._interface_modes[interface] = WifiInterfaceMode.NORMAL
            self._save_interface_mode(interface, WifiInterfaceMode.NORMAL)
            await self._set_interface_managed(interface, True)

    async def disable_hotspot_on_interface(self, interface: str, save_settings: bool = True) -> None:
        """Disable hotspot on a specific interface."""
        if interface in self._create_ap_processes:
            process = self._create_ap_processes[interface]
            if process.poll() is None:
                process.terminate()
                process.wait()
            del self._create_ap_processes[interface]
            logger.info(f"Stopped create_ap process on {interface}")

        virtual_ap_name = get_virtual_ap_name(interface)
        await self._cleanup_virtual_interface_for(virtual_ap_name)

        # Reset interface from AP mode back to managed/station mode
        # This is required because we set type __ap before starting create_ap
        subprocess.run(["ip", "link", "set", interface, "down"], check=False, capture_output=True)
        subprocess.run(["iw", "dev", interface, "set", "type", "managed"], check=False, capture_output=True)
        subprocess.run(["ip", "link", "set", interface, "up"], check=False, capture_output=True)
        await asyncio.sleep(0.5)  # Give interface time to come up

        # Restore NetworkManager control of the interface (if it was released for direct AP mode)
        await self._set_interface_managed(interface, True)

        if self._hotspot_interface == interface:
            self._hotspot_interface = None
            self._create_ap_process = None

        if save_settings and not self._create_ap_processes:
            self._settings_manager.settings.hotspot_enabled = False
            self._settings_manager.save()

    async def disable_hotspot(self, save_settings: bool = True) -> None:
        """Disable hotspot (backward compatible - stops all hotspots)."""
        for interface in list(self._create_ap_processes.keys()):
            await self.disable_hotspot_on_interface(interface, save_settings=False)

        # Also handle legacy single process
        if self._create_ap_process:
            self._create_ap_process.terminate()
            self._create_ap_process.wait()
            self._create_ap_process = None
            logger.info("Stopped legacy create_ap process")

        await self._cleanup_virtual_interface()

        if save_settings:
            self._settings_manager.settings.hotspot_enabled = False
            self._settings_manager.save()

    async def hotspot_is_running_on_interface(self, interface: str) -> bool:
        """Check if hotspot is running on a specific interface."""
        if interface in self._create_ap_processes:
            return self._create_ap_processes[interface].poll() is None
        return False

    async def hotspot_is_running(self) -> bool:
        """Check if any hotspot is running (backward compatible)."""
        for process in self._create_ap_processes.values():
            if process.poll() is None:
                return True
        return self._create_ap_process is not None and self._create_ap_process.poll() is None

    async def get_hotspot_interface(self) -> Optional[str]:
        """Get the interface currently running hotspot, or None if no hotspot is running."""
        for interface, process in self._create_ap_processes.items():
            if process.poll() is None:
                return interface
        return None

    async def supports_hotspot(self) -> bool:
        return True

    # pylint: disable=too-many-return-statements
    async def supports_hotspot_on_interface(self, interface: str) -> bool:
        """Check if hotspot is supported on a specific interface.

        Verifies the interface exists, supports AP mode, AND can run AP + managed simultaneously.
        Some adapters support AP mode but can't create virtual interfaces while connected.
        """
        if interface not in self._device_paths:
            return False

        try:
            # Get the phy name for this interface
            result = subprocess.run(
                ["iw", "dev", interface, "info"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False

            # Parse phy name from output (e.g., "wiphy 0" -> "phy0")
            phy_name = None
            for line in result.stdout.split("\n"):
                if "wiphy" in line:
                    phy_num = line.strip().split()[-1]
                    phy_name = f"phy{phy_num}"
                    break

            if not phy_name:
                return False

            # Check phy capabilities
            result = subprocess.run(
                ["iw", "phy", phy_name, "info"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False

            phy_info = result.stdout

            # Check 1: Must support AP mode
            supports_ap = False
            in_modes_section = False
            for line in phy_info.split("\n"):
                if "Supported interface modes:" in line:
                    in_modes_section = True
                    continue
                if in_modes_section:
                    if line.strip().startswith("*"):
                        if "AP" in line and "AP/VLAN" not in line:
                            supports_ap = True
                            break
                    else:
                        break

            if not supports_ap:
                return False

            # Check 2: Must support interface combinations (managed + AP simultaneously)
            # If "interface combinations are not supported" is present, can't run virtual AP
            if "interface combinations are not supported" in phy_info:
                logger.info(f"{interface}: AP mode supported but interface combinations not supported")
                return False

            # Check 3: Look for valid combinations that include both managed and AP
            # e.g., "#{ managed } <= 1, #{ AP } <= 1"
            if "valid interface combinations:" in phy_info:
                # Has interface combinations - check if managed + AP is allowed
                combo_section = phy_info.split("valid interface combinations:")[1]
                combo_section = combo_section.split("Device supports")[0]  # End at next section
                if "managed" in combo_section and "AP" in combo_section:
                    return True

            return False
        except Exception as e:
            logger.warning(f"Failed to check AP mode support for {interface}: {e}")
            return False

    async def _check_interface_supports_ap_mode(self, interface: str) -> bool:
        """Check if interface hardware supports AP mode (regardless of dual mode support)."""
        if interface not in self._device_paths:
            return False

        try:
            result = subprocess.run(["iw", "dev", interface, "info"], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return False

            phy_name = None
            for line in result.stdout.split("\n"):
                if "wiphy" in line:
                    phy_num = line.strip().split()[-1]
                    phy_name = f"phy{phy_num}"
                    break

            if not phy_name:
                return False

            result = subprocess.run(["iw", "phy", phy_name, "info"], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return False

            in_modes_section = False
            for line in result.stdout.split("\n"):
                if "Supported interface modes:" in line:
                    in_modes_section = True
                    continue
                if in_modes_section:
                    if line.strip().startswith("*"):
                        if "AP" in line and "AP/VLAN" not in line:
                            return True
                    else:
                        break

            return False
        except Exception:
            return False

    async def _check_interface_supports_dual_mode(self, interface: str) -> bool:
        """Check if interface can run managed + AP simultaneously (requires virtual interface support)."""
        # This is the same as supports_hotspot_on_interface for now
        return await self.supports_hotspot_on_interface(interface)

    async def get_interface_capabilities(self, interface: str) -> WifiInterfaceCapabilities:
        """Get hardware capabilities for an interface."""
        current_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)

        # If interface is currently in HOTSPOT mode (direct AP, not dual), we know it supports AP
        # but can't check dual mode support since interface is unmanaged
        if current_mode == WifiInterfaceMode.HOTSPOT and interface in self._create_ap_processes:
            process = self._create_ap_processes[interface]
            if process.poll() is None:  # Process is running
                # Interface is in direct hotspot mode - we know it supports AP
                return WifiInterfaceCapabilities(
                    interface=interface,
                    supports_ap_mode=True,
                    supports_dual_mode=False,  # Direct mode doesn't support dual
                    current_mode=current_mode,
                    available_modes=[WifiInterfaceMode.NORMAL, WifiInterfaceMode.HOTSPOT],
                )

        supports_ap = await self._check_interface_supports_ap_mode(interface)
        supports_dual = await self._check_interface_supports_dual_mode(interface)

        available_modes = [WifiInterfaceMode.NORMAL]
        if supports_ap:
            available_modes.append(WifiInterfaceMode.HOTSPOT)
        if supports_dual:
            available_modes.append(WifiInterfaceMode.DUAL)

        return WifiInterfaceCapabilities(
            interface=interface,
            supports_ap_mode=supports_ap,
            supports_dual_mode=supports_dual,
            current_mode=current_mode,
            available_modes=available_modes,
        )

    async def get_interface_mode(self, interface: str) -> WifiInterfaceMode:
        """Get current operating mode for an interface."""
        return self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)

    async def set_interface_mode(self, interface: str, mode: WifiInterfaceMode) -> bool:
        """Set the operating mode for an interface.

        - NORMAL: Client mode only, disable hotspot if running
        - HOTSPOT: AP mode only, disconnect from any network, use interface directly as AP
        - DUAL: Both simultaneously using virtual interface (requires hardware support)
        """
        # Interface can be in _device_paths (managed) or _create_ap_processes (unmanaged hotspot)
        is_known = interface in self._device_paths or interface in self._create_ap_processes
        if not is_known:
            logger.error(f"Interface {interface} not found")
            return False

        caps = await self.get_interface_capabilities(interface)
        if mode not in caps.available_modes:
            logger.error(f"Mode {mode} not supported on {interface}. Available: {caps.available_modes}")
            return False

        current_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)
        if current_mode == mode:
            logger.info(f"{interface} already in {mode} mode")
            return True

        logger.info(f"Switching {interface} from {current_mode} to {mode}")

        # Disable hotspot if currently running on this interface
        if await self.hotspot_is_running_on_interface(interface):
            await self.disable_hotspot_on_interface(interface, save_settings=False)

        if mode == WifiInterfaceMode.NORMAL:
            # Just disable hotspot (already done above), interface returns to normal
            self._interface_modes[interface] = mode
            self._save_interface_mode(interface, mode)
            return True

        if mode == WifiInterfaceMode.HOTSPOT:
            # Disconnect from any network first (ignore errors if not connected)
            try:
                await self.disconnect_interface(interface)
            except Exception as e:
                logger.debug(f"Disconnect before hotspot mode (expected if not connected): {e}")
            # Enable hotspot in "direct" mode (no virtual interface)
            success = await self._enable_hotspot_direct(interface)
            if success:
                self._interface_modes[interface] = mode
                self._save_interface_mode(interface, mode)
            return success

        # mode == WifiInterfaceMode.DUAL
        # Enable hotspot using virtual interface (existing behavior)
        success = await self.enable_hotspot_on_interface(interface, save_settings=True)
        if success:
            self._interface_modes[interface] = mode
            self._save_interface_mode(interface, mode)
        return success

    async def _enable_hotspot_direct(self, interface: str, save_settings: bool = True) -> bool:
        """Enable hotspot directly on the interface (not using virtual interface).

        This is used for adapters that support AP mode but not interface combinations.
        The interface itself becomes the AP, so it cannot be connected to a network.
        """
        if save_settings:
            self._settings_manager.settings.hotspot_enabled = True
            self._settings_manager.save()

        credentials = self.hotspot_credentials_for_interface(interface)
        gateway = get_hotspot_gateway(interface)

        cmd = [
            "create_ap",
            "--no-virt",  # Don't create virtual interface
            "-n",  # No internet sharing
            "-g",
            gateway,
            "--freq-band",
            "2.4",
            "-c",
            "6",  # Use channel 6 for 2.4GHz
            interface,  # Use physical interface directly
            credentials.ssid,
            credentials.password,
        ]

        try:
            # Stop existing hotspot on this interface if running
            if interface in self._create_ap_processes:
                existing_process = self._create_ap_processes[interface]
                if existing_process.poll() is None:
                    logger.info(f"Stopping existing hotspot on {interface}...")
                    existing_process.terminate()
                    existing_process.wait()
                del self._create_ap_processes[interface]

            # Clean up any stale processes from previous attempts (e.g., after crash)
            # Kill any orphaned create_ap/dnsmasq using this interface's gateway
            subprocess.run(["pkill", "-f", f"create_ap.*{interface}"], check=False, capture_output=True)
            subprocess.run(["pkill", "-f", f"dnsmasq.*{gateway}"], check=False, capture_output=True)
            # Remove stale temp directories
            subprocess.run(["sh", "-c", f"rm -rf /tmp/create_ap.{interface}.conf.*"], check=False, capture_output=True)
            await asyncio.sleep(0.2)  # Brief pause to let processes terminate

            # Release interface from NetworkManager before create_ap can take over
            await self._set_interface_managed(interface, False)

            # Set interface to AP mode before starting create_ap
            # Some drivers (like rtl8192eu) require explicit mode switch
            subprocess.run(["ip", "link", "set", interface, "down"], check=False, capture_output=True)
            set_type_result = subprocess.run(
                ["iw", "dev", interface, "set", "type", "__ap"], check=False, capture_output=True, text=True
            )
            if set_type_result.returncode != 0:
                logger.warning(f"Failed to set {interface} to AP mode: {set_type_result.stderr}")
            subprocess.run(["ip", "link", "set", interface, "up"], check=False, capture_output=True)
            await asyncio.sleep(0.5)

            # Verify interface is in AP mode
            verify_result = subprocess.run(
                ["iw", "dev", interface, "info"], check=False, capture_output=True, text=True
            )
            if "type AP" not in verify_result.stdout:
                logger.warning(f"Interface {interface} not in AP mode after setup. Info: {verify_result.stdout}")

            # pylint: disable=consider-using-with
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1
            )
            # pylint: enable=consider-using-with

            # Add to cache immediately so interface shows up in get_wifi_interfaces during startup
            self._create_ap_processes[interface] = process
            self._hotspot_interface = interface

            success = False
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            timeout = 30

            while process.poll() is None:
                if select.select([process.stdout], [], [], 0)[0]:
                    assert process.stdout is not None
                    line = process.stdout.readline()

                    line = line.strip()
                    if line:
                        logger.info(f"create_ap ({interface} direct): {line}")
                        # Accept both "AP-ENABLED" and "UNINITIALIZED->ENABLED" as success
                        # Some adapters take a long time between ENABLED and AP-ENABLED
                        if "Done" in line or "AP-ENABLED" in line or "->ENABLED" in line:
                            success = True
                            break
                        if "ERROR" in line:
                            logger.error(f"create_ap error on {interface}: {line}")
                            await self._cleanup_failed_direct_hotspot(interface, process)
                            return False

                    if loop.time() - start_time > timeout:
                        logger.error(f"Timeout waiting for create_ap on {interface}")
                        await self._cleanup_failed_direct_hotspot(interface, process)
                        return False

                await asyncio.sleep(0.1)

            if not success:
                exit_code = process.poll()
                # Read any remaining output to understand why it failed
                remaining_output = ""
                if process.stdout:
                    remaining_output = process.stdout.read()
                logger.error(
                    f"Failed to start create_ap directly on {interface}, exit code: {exit_code}. "
                    f"Remaining output: {remaining_output}"
                )
                await self._cleanup_failed_direct_hotspot(interface, process)
                return False

            logger.info(f"Successfully started create_ap directly on {interface} with PID {process.pid}")
            self._create_ap_process = process  # Backward compatibility

            self._tasks.append(loop.create_task(self._monitor_create_ap_output(process, interface)))

            logger.info(f"Hotspot enabled directly on {interface}")
            return True

        except Exception as e:
            logger.error(f"Failed to start direct hotspot on {interface}: {e}")
            # Clean up on exception
            if interface in self._create_ap_processes:
                del self._create_ap_processes[interface]
            await self._set_interface_managed(interface, True)
            return False

    async def _cleanup_failed_direct_hotspot(self, interface: str, process: subprocess.Popen[str]) -> None:
        """Clean up after a failed direct hotspot attempt."""
        if process.poll() is None:
            process.terminate()
            process.wait()
        if interface in self._create_ap_processes:
            del self._create_ap_processes[interface]
        if self._hotspot_interface == interface:
            self._hotspot_interface = None
        # Restore NetworkManager control
        await self._set_interface_managed(interface, True)

    async def status(self) -> WifiStatus:
        """Get status of primary interface (backward compatible)."""
        if not self._device_path:
            return WifiStatus(state="disconnected")

        device = NetworkDeviceWireless(self._device_path, self._bus)
        state = await device.state

        if state == DeviceState.ACTIVATED:
            try:
                ap_path = await device.active_access_point
                if not ap_path or ap_path == "/":
                    return WifiStatus(state="connecting")
                ap = AccessPoint(ap_path, self._bus)
                ssid: bytes = await ap.ssid
                ip4_conf_path = await device.ip4_config

                status = {
                    "state": "connected",
                    "ssid": ssid.decode("utf-8"),
                    "wpa_state": "COMPLETED",
                    "key_mgmt": "WPA-PSK",
                }

                if ip4_conf_path and ip4_conf_path != "/":
                    ip4_conf = IPv4Config(ip4_conf_path, self._bus)
                    address_data = await ip4_conf.address_data
                    if address_data:
                        status["ip_address"] = address_data[0]["address"][1]

                return WifiStatus(**status)
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                return WifiStatus(state="disconnected")
        return WifiStatus(state="disconnected")

    async def get_saved_wifi_network(self) -> List[SavedWifiNetwork]:
        if not self._nm_settings:
            return []

        saved_networks: List[SavedWifiNetwork] = []
        try:
            for conn_path in await self._nm_settings.connections:
                try:
                    settings = NetworkConnectionSettings(conn_path, self._bus)
                    profile = await settings.get_profile(fetch_secrets=False)

                    if not profile.wireless or not profile.wireless.ssid:
                        continue

                    ssid = profile.wireless.ssid.decode("utf-8")
                    saved_networks.append(
                        SavedWifiNetwork(
                            networkid=0,
                            ssid=ssid,
                            bssid=profile.wireless.bssid,
                            nm_id=conn_path,
                            nm_uuid=profile.connection.uuid,
                        )
                    )
                except Exception as e:
                    logger.error(f"Error processing connection {conn_path}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error getting saved networks: {e}")
            return []
        return saved_networks

    async def set_hotspot_credentials(self, credentials: WifiCredentials) -> None:
        """Set global hotspot credentials (for backward compatibility with v1 API).
        This sets credentials for wlan0 and restarts all hotspots.
        """
        await self.set_hotspot_credentials_for_interface("wlan0", credentials)

    async def set_hotspot_credentials_for_interface(
        self, interface: str, credentials: WifiCredentials, restart_hotspot: bool = True
    ) -> None:
        """Set hotspot credentials for a specific interface."""
        self._settings_manager.settings.set_interface_hotspot_credentials(
            interface, credentials.ssid, credentials.password
        )
        self._settings_manager.save()
        logger.info(f"Saved hotspot credentials for {interface}: SSID={credentials.ssid}")

        if not restart_hotspot:
            return

        # Only restart the hotspot on this interface if it's running
        if interface in self._create_ap_processes:
            process = self._create_ap_processes[interface]
            if process.poll() is None:
                mode = self._interface_modes.get(interface, WifiInterfaceMode.HOTSPOT)
                logger.info(f"Restarting hotspot on {interface} with new credentials")

                # Disable hotspot on this interface
                await self.disable_hotspot_on_interface(interface, save_settings=False)

                # Re-enable with new credentials
                if mode == WifiInterfaceMode.HOTSPOT:
                    await self._enable_hotspot_direct(interface, save_settings=False)
                    self._interface_modes[interface] = mode
                elif mode == WifiInterfaceMode.DUAL:
                    await self.enable_hotspot_on_interface(interface, save_settings=False)
                    self._interface_modes[interface] = mode

    def hotspot_credentials(self) -> WifiCredentials:
        """Get global hotspot credentials (for backward compatibility with v1 API)."""
        return self.hotspot_credentials_for_interface("wlan0")

    def hotspot_credentials_for_interface(self, interface: str) -> WifiCredentials:
        """Get hotspot credentials for a specific interface."""
        # Check for per-interface credentials first
        creds = self._settings_manager.settings.get_interface_hotspot_credentials(interface)
        if creds:
            return WifiCredentials(ssid=creds["ssid"], password=creds["password"])

        # Fall back to global credentials (for backward compatibility)
        if self._settings_manager.settings.hotspot_ssid and self._settings_manager.settings.hotspot_password:
            return WifiCredentials(
                ssid=self._settings_manager.settings.hotspot_ssid,
                password=self._settings_manager.settings.hotspot_password,
            )

        # Generate default credentials with unique suffix per interface
        try:
            dev_id = device_id()
        except Exception:
            dev_id = "000000"
        hashed_id = hashlib.md5(dev_id.encode()).hexdigest()[:6]

        # Add interface suffix for non-primary interfaces
        if interface != "wlan0":
            match = re.search(r"\d+$", interface)
            suffix = f"-{match.group()}" if match else f"-{interface}"
            ssid = f"BlueOS ({hashed_id}){suffix}"
        else:
            ssid = f"BlueOS ({hashed_id})"

        return WifiCredentials(ssid=ssid, password="blueosap")

    async def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        logger.info("Starting NetworkManagerWifi cleanup")

        # Disable hotspot first to stop any running processes
        await self.disable_hotspot(save_settings=False)

        # Cancel all background tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, CancelledError):
                    pass
                except Exception as e:
                    logger.error(f"Error while cancelling task: {e}")
        self._tasks.clear()

        # Cleanup virtual interface
        await self._cleanup_virtual_interface()

        # Close bus connection
        if self._bus:
            self._bus.close()

        # cleanup create_ap
        if self._create_ap_process:
            self._create_ap_process.terminate()
            try:
                self._create_ap_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._create_ap_process.kill()
                self._create_ap_process.wait()
            self._create_ap_process = None

        logger.info("NetworkManagerWifi cleanup completed")

    async def handle_shutdown(self, sig: signal.Signals) -> None:
        """Handle shutdown signals gracefully"""
        logger.info(f"Received shutdown signal {sig.name}")
        await self.cleanup()

    async def disconnect(self) -> None:
        """Disconnect from current wifi network (primary interface)."""
        primary_interface = None
        for name, path in list(self._device_paths.items()):
            if path == self._device_path:
                primary_interface = name
                break

        if primary_interface:
            await self.disconnect_interface(primary_interface)

    async def can_work(self) -> bool:
        try:
            NetworkManager(self._bus)
        except Exception as e:
            logger.info(f"NetworkManager not available: {e}")
            return False
        return True

    def disable_smart_hotspot(self) -> None:
        """Disable the smart hotspot feature."""
        self._settings_manager.settings.smart_hotspot_enabled = False
        self._settings_manager.save()
        logger.info("Smart hotspot disabled")

    def enable_smart_hotspot(self) -> None:
        """Enable the smart hotspot feature."""
        self._settings_manager.settings.smart_hotspot_enabled = True
        self._settings_manager.save()
        logger.info("Smart hotspot enabled")

    async def get_current_network(self) -> Optional[SavedWifiNetwork]:
        raise NotImplementedError

    def is_smart_hotspot_enabled(self) -> bool:
        return self._settings_manager.settings.smart_hotspot_enabled is True

    async def remove_network(self, _network_id: str) -> None:
        networks = await self.get_saved_wifi_network()
        network = next(filter(lambda net: net.ssid == _network_id, networks), None)
        if network is not None and network.nm_uuid is not None and self._nm_settings is not None:
            logger.info(f"Forgetting network {network}")
            await self._nm_settings.delete_connection_by_uuid(network.nm_uuid)

    async def hotspot_watchdog(self) -> None:
        """
        This takes care of the smart-hotspot feature. It will enable the hotspot if we stay disconnected for longer than 30 seconds
        """
        if self._settings_manager.settings.hotspot_enabled in [True, None]:
            await asyncio.sleep(5)
            await self.enable_hotspot()
        while True:
            await asyncio.sleep(30)
            if not self._settings_manager.settings.smart_hotspot_enabled:
                continue

            state = await self.status()
            if state.state == "connected":
                continue

            if not await self.hotspot_is_running():
                logger.info("No network connection detected, enabling hotspot")
                await self.enable_hotspot()

            # Check health of all hotspot interfaces
            await self._check_hotspot_health()

    async def _get_interface_type(self, interface: str) -> Optional[str]:
        """Get the current interface type using iw command."""
        try:
            result = await asyncio.create_subprocess_exec(
                "iw",
                "dev",
                interface,
                "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            output = stdout.decode()
            for line in output.split("\n"):
                if "type" in line:
                    # Line format: "\t\ttype AP" or "\t\ttype managed"
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        return parts[1]
        except Exception as e:
            logger.debug(f"Failed to get interface type for {interface}: {e}")
        return None

    async def _check_hotspot_health(self) -> None:
        """Check that interfaces in hotspot mode are actually in AP mode."""
        for interface, process in list(self._create_ap_processes.items()):
            # Skip if process is dead (will be cleaned up elsewhere)
            if process.poll() is not None:
                continue

            # Check if interface is in AP mode
            iface_type = await self._get_interface_type(interface)
            if iface_type is None:
                continue

            expected_mode = self._interface_modes.get(interface, WifiInterfaceMode.NORMAL)
            if expected_mode in (WifiInterfaceMode.HOTSPOT, WifiInterfaceMode.DUAL) and iface_type != "AP":
                logger.warning(f"Hotspot on {interface} has invalid type '{iface_type}' (expected AP) - restarting")
                # Kill the stuck process
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

                # Remove from tracking
                if interface in self._create_ap_processes:
                    del self._create_ap_processes[interface]

                # Restart the hotspot
                asyncio.create_task(self._restart_hotspot_after_failure(interface))
