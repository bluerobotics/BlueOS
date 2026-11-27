import abc
import asyncio
import functools
from argparse import ArgumentParser, Namespace
from typing import List, Optional

import radio
from commonwealth.settings.manager import PydanticManager
from settings import SettingsV1
from typedefs import (
    RfkillStatus,
    SavedWifiNetwork,
    ScannedWifiNetwork,
    WifiCredentials,
    WifiStatus,
)
from wifi_handlers.wpa_supplicant.wpa_supplicant import WPASupplicant


@functools.cache
def _country_lock() -> asyncio.Lock:
    # Created on first use, so it binds to the running loop and not to whichever one exists at import
    return asyncio.Lock()


class AbstractWifiManager:
    wpa = WPASupplicant()

    def __init__(self) -> None:
        self._settings_manager: PydanticManager[SettingsV1] = PydanticManager("wifi-manager", SettingsV1)
        self._settings_manager.load()

    @abc.abstractmethod
    async def can_work(self) -> bool:
        """Check if the given wifi manager has the necessary tools/interfaces to work"""
        return True

    @abc.abstractmethod
    async def get_wifi_available(self) -> List[ScannedWifiNetwork]:
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
    async def try_connect_to_network(self, credentials: WifiCredentials, hidden: bool = False) -> None:
        """Try to connect to a network"""
        raise NotImplementedError

    @abc.abstractmethod
    async def status(self) -> WifiStatus:
        """Check wpa_supplicant status"""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """

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

    async def set_country(self, code: str) -> None:
        # A failure restores the previous country, which overlapping requests would mix up
        async with _country_lock():
            await self._apply_country(code)

    async def _apply_country(self, code: str) -> None:
        # Choosing a country implies the user wants the radio on, as raspi-config does
        await self.rfkill_unblock()
        await radio.set_country(code)
        previous_country = self._settings_manager.settings.regulatory_country
        if previous_country == code:
            return
        self._settings_manager.settings.regulatory_country = code
        try:
            self._settings_manager.save()
        except Exception:
            # Or a later unrelated save would persist a country the request failed to apply
            self._settings_manager.settings.regulatory_country = previous_country
            raise

    async def apply_saved_country(self) -> None:
        # Never forcing a default: the country can already have been set by the user outside of BlueOS
        saved_country = self._settings_manager.settings.regulatory_country
        # Skipping when it is already active also avoids rewriting wpa_supplicant.conf on every boot
        if saved_country is not None and await radio.current_country() != saved_country:
            await self.set_country(saved_country)

    async def rfkill_status(self) -> RfkillStatus:
        return await radio.rfkill_status()

    async def rfkill_unblock(self) -> None:
        await radio.rfkill_unblock()

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the wifi manager"""
        raise NotImplementedError

    def configure(self, _parser: Namespace) -> None:
        """Configure the wifi manager"""

    def add_arguments(self, _parser: ArgumentParser) -> None:
        """Add arguments to the parser"""
