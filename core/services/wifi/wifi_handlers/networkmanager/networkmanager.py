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
        # Store all WiFi device paths, keyed by interface name
        self._device_paths: Dict[str, str] = {}
        # Primary device for backward compatibility (first WiFi device found)
        self._device_path: Optional[str] = None
        # Hotspot processes per interface
        self._create_ap_processes: Dict[str, subprocess.Popen[str]] = {}
        # For backward compatibility
        self._create_ap_process: Optional[subprocess.Popen[str]] = None
        self._ap_interface = VIRTUAL_AP_INTERFACE
        # Track which interface is running hotspot
        self._hotspot_interface: Optional[str] = None
        self._tasks: List[asyncio.Task[Any]] = []
        self._nm = NetworkManager(self._bus)
        self._nm_settings = NetworkManagerSettings(self._bus)
        logger.info("NetworkManagerWifi initialized")

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
        self._tasks.append(asyncio.get_event_loop().create_task(self._autoscan()))
        self._tasks.append(asyncio.get_event_loop().create_task(self.hotspot_watchdog()))

    async def _autoscan(self) -> None:
        """Periodically scan for networks on all interfaces."""
        while True:
            for interface_name, device_path in self._device_paths.items():
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

        for interface_name, device_path in self._device_paths.items():
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

                interfaces.append(
                    WifiInterface(
                        name=interface_name,
                        connected=connected,
                        ssid=ssid,
                        signal_strength=signal_strength,
                        ip_address=ip_address,
                        mac_address=mac_address,
                    )
                )
            except Exception as e:
                logger.error(f"Error getting status for {interface_name}: {e}")

        return interfaces

    # pylint: disable=too-many-locals
    async def get_interface_status(self, interface_name: str) -> Optional[WifiInterface]:
        """Get status for a specific interface."""
        device_path = self._device_paths.get(interface_name)
        if not device_path:
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

            return WifiInterface(
                name=interface_name,
                connected=connected,
                ssid=ssid,
                signal_strength=signal_strength,
                ip_address=ip_address,
                mac_address=mac_address,
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

        for interface_name, device_path in self._device_paths.items():
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

                wpa_flags = await ap.wpa_flags.get_async()
                rsn_flags = await ap.rsn_flags.get_async()
                flags = await ap.flags.get_async()

                security_flags = []

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
                ap = AccessPoint(await device.active_access_point, self._bus)
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

        for interface_name in self._device_paths:
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
        for name, path in self._device_paths.items():
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

                    if not credentials.password:
                        logger.info(f"Found existing connection for {credentials.ssid} (no password check)")
                        return str(conn_path)

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

        credentials = self.hotspot_credentials()

        cmd = [
            "create_ap",
            "-n",
            virtual_ap_name,
            "-g",
            "192.168.42.1",
            "--redirect-to-localhost",
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

            success = False
            start_time = asyncio.get_event_loop().time()
            timeout = 30
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

                    if asyncio.get_event_loop().time() - start_time > timeout:
                        logger.error(f"Timeout waiting for create_ap on {interface}")
                        return success

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

            self._tasks.append(asyncio.get_event_loop().create_task(self._monitor_create_ap_output(process)))

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

    async def _monitor_create_ap_output(self, process: subprocess.Popen[str]) -> None:
        """Monitor create_ap process output non-blockingly using select"""
        try:
            while True:
                if select.select([process.stdout], [], [], 0)[0]:
                    assert process.stdout is not None
                    if line := process.stdout.readline().strip():
                        logger.info(f"create_ap: {line}")

                if process.poll() is not None:
                    break

                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error monitoring create_ap output: {e}")
        finally:
            logger.info("create_ap process monitoring ended")
            if process == self._create_ap_process:
                self._create_ap_process = None

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

    async def supports_hotspot_on_interface(self, interface: str) -> bool:
        """Check if hotspot is supported on a specific interface."""
        return interface in self._device_paths

    async def status(self) -> WifiStatus:
        """Get status of primary interface (backward compatible)."""
        if not self._device_path:
            return WifiStatus(state="disconnected")

        device = NetworkDeviceWireless(self._device_path, self._bus)
        state = await device.state

        if state == DeviceState.ACTIVATED:
            try:
                ap = AccessPoint(await device.active_access_point, self._bus)
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
        self._settings_manager.settings.hotspot_ssid = credentials.ssid
        self._settings_manager.settings.hotspot_password = credentials.password
        self._settings_manager.save()
        await self.disable_hotspot(save_settings=False)
        await self.enable_hotspot()

    def hotspot_credentials(self) -> WifiCredentials:
        try:
            dev_id = device_id()
        except Exception:
            dev_id = "000000"
        hashed_id = hashlib.md5(dev_id.encode()).hexdigest()[:6]

        return WifiCredentials(
            ssid=self._settings_manager.settings.hotspot_ssid or f"BlueOS ({hashed_id})",
            password=self._settings_manager.settings.hotspot_password or "blueosap",
        )

    async def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        logger.info("Starting NetworkManagerWifi cleanup")

        await self.disable_hotspot(save_settings=False)

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

        await self._cleanup_virtual_interface()

        if self._bus:
            self._bus.close()

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
        for name, path in self._device_paths.items():
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
        """Takes care of the smart-hotspot feature."""
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
