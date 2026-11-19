import abc
from argparse import ArgumentParser, Namespace
from typing import List, Optional

from commonwealth.settings.manager import PydanticManager
from exceptions import InterfaceNotFound
from settings import SettingsV2
from typedefs import SavedWifiNetwork, ScannedWifiNetwork, WifiCredentials, WifiStatus
from wifi_handlers.wpa_supplicant.wpa_supplicant import WPASupplicant


class AbstractWifiManager:
    wpa = WPASupplicant()

    def __init__(self) -> None:
        self._settings_manager: PydanticManager[SettingsV2] = PydanticManager("wifi-manager", SettingsV2)
        self._settings_manager.load()

    @abc.abstractmethod
    async def can_work(self) -> bool:
        """Check if the given wifi manager has the necessary tools/interfaces to work"""
        return True

    @abc.abstractmethod
    async def get_interfaces(self) -> List[str]:
        """Get the names of the wifi interfaces, the first one is the default for interface-less requests"""
        raise NotImplementedError

    async def validate_interface(self, interface: Optional[str]) -> None:
        if interface is not None and interface not in await self.get_interfaces():
            raise InterfaceNotFound(interface)

    @abc.abstractmethod
    async def hotspot_interface(self) -> Optional[str]:
        """Get the wifi interface that hosts the hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    async def set_hotspot_interface(self, interface: str) -> None:
        """Set the wifi interface that hosts the hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_wifi_available(self, interface: Optional[str] = None) -> List[ScannedWifiNetwork]:
        """Get a dict from the wifi signals available"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_saved_wifi_network(self) -> List[SavedWifiNetwork]:
        """Get a list of saved wifi networks"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_current_network(self) -> Optional[SavedWifiNetwork]:
        """Get current network, if connected."""
        raise NotImplementedError

    @abc.abstractmethod
    async def hotspot_is_running(self) -> bool:
        """Check if the hotspot is running."""
        raise NotImplementedError

    @abc.abstractmethod
    async def supports_hotspot(self) -> bool:
        """Check if the wifi manager supports hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    async def set_hotspot_credentials(self, _credentials: WifiCredentials) -> None:
        """Set the hotspot credentials."""
        raise NotImplementedError

    @abc.abstractmethod
    async def try_connect_to_network(
        self, credentials: WifiCredentials, hidden: bool = False, interface: Optional[str] = None
    ) -> None:
        """Try to connect to a network"""
        raise NotImplementedError

    @abc.abstractmethod
    async def status(self, interface: Optional[str] = None) -> WifiStatus:
        """Check wpa_supplicant status"""
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self, interface: Optional[str] = None) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def remove_network(self, ssid: str) -> None:
        """Remove a network from the wpa_supplicant conf file"""
        raise NotImplementedError

    @abc.abstractmethod
    def hotspot_credentials(self) -> WifiCredentials:
        """Get the hotspot credentials."""
        raise NotImplementedError

    @abc.abstractmethod
    async def enable_hotspot(self, _save_settings: bool = True) -> bool:
        """Enable the hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    async def disable_hotspot(self, _save_settings: bool = True) -> None:
        """Disable the hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    def enable_smart_hotspot(self) -> None:
        """Enables the hotspot if there's no internet connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def disable_smart_hotspot(self) -> None:
        """Disable the smart hotspot."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_smart_hotspot_enabled(self) -> bool:
        return self._settings_manager.settings.smart_hotspot_enabled is True

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the wifi manager"""
        raise NotImplementedError

    def configure(self, _parser: Namespace) -> None:
        """Configure the wifi manager"""

    def add_arguments(self, _parser: ArgumentParser) -> None:
        """Add arguments to the parser"""
