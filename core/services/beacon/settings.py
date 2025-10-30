import json
import re
import socket
from typing import Any, Dict, List, Literal, Optional

import psutil
from commonwealth.settings.settings import PydanticSettings
from loguru import logger
from pydantic import BaseModel, Field


class InvalidIpAddress(Exception):
    pass


class DefaultSettings(BaseModel):
    domain_names: List[str]
    advertise: List[str]
    ip: str


class Interface(BaseModel):
    name: str
    domain_names: List[str]
    advertise: List[str]
    ip: str

    def get_phys(self) -> List[psutil._common.snicaddr]:
        """
        return Physical interface from psutil
        """
        return list(filter(lambda address: address.family == socket.AF_INET, psutil.net_if_addrs()[self.name]))

    def get_ip_strs(self) -> List[str]:
        """
        returns a list of the interface IPs (IPv4 only) as a list of strings:
        - if self.ip is "ips[*]", it returns all ips of that interface
        - if self.ip is "ips[n]", it returns the n-th ip of that interface
        - if self.ip is a single ipv4 (like "192.168.2.2"), it returns that ip as a string
        - if self.ip is (mistakenly) an IPv6 or any other non-IPv4 format, it raises an InvalidIpAddress error
        """
        address = str(self.ip)
        # Check for 'ips[n]'

        if address == "ips[*]":
            addresses = []
            for iface in self.get_phys():
                try:
                    addresses.append(str(iface.address))
                except Exception as e:
                    logger.warning(f"unable to add ip {iface.address}: {e}")
            return addresses
        matches = re.findall(r"ips\[(\d+)]", self.ip)
        if len(matches) != 0:
            index = int(matches[0])
            try:
                address = str(self.get_phys()[index].address)
            except Exception as e:
                logger.warning(f"unable to get {index}-th IP address: {e}")
                return []
        # Validate ip
        try:
            socket.inet_aton(address)
            return [address]
        except OSError as e:
            raise InvalidIpAddress(f"Invalid IP address: {address}") from e

    def get_ips(self) -> List[bytes]:
        """
        returns a list of the interface IPs (IPv4 only) as a list of 4 bytes
        """
        return [socket.inet_aton(ip) for ip in self.get_ip_strs()]

    def __repr__(self) -> str:
        return str(self.name)


class ServiceTypes(BaseModel):
    name: str
    protocol: Literal["_udp", "_tcp"]
    port: int
    properties: Optional[str] = None

    def get_properties(self) -> Dict[str, Any]:
        if self.properties is None:
            return {}
        return json.loads(self.properties)  # type: ignore


class SettingsV1(PydanticSettings):
    default: DefaultSettings = Field(default_factory=lambda: DefaultSettings(domain_names=[], advertise=[], ip=""))
    blacklist: List[str] = Field(default_factory=list)
    interfaces: List[Interface] = Field(default_factory=list)
    advertisement_types: List[ServiceTypes] = Field(default_factory=list)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION

    def get_interface_or_create_default(self, name: str) -> Interface:
        """
        tries to return settings for the given interface, creates a new Interface object
        based on the default settings if unable to find it.
        """
        found = [interface for interface in self.interfaces if interface.name == name]
        if found:
            assert isinstance(found[0], Interface)
            return found[0]
        new = Interface(
            name=name, domain_names=self.default.domain_names, advertise=self.default.advertise, ip=self.default.ip
        )
        self.interfaces.append(new)
        return new


class SettingsV2(SettingsV1):
    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            super().migrate(data)

        data["default"]["domain_names"] = [domain for domain in data["default"]["domain_names"] if domain != "blueos"]
        try:
            for interface in data["interfaces"]:
                if interface["name"] == "wlan0":
                    interface["domain_names"] = [
                        name for name in interface["domain_names"] if name not in ["blueos", "companion"]
                    ]
        except Exception as e:
            logger.error(f"unable to update SettingsV1 to SettingsV2: {e}")

        data["VERSION"] = SettingsV2.STATIC_VERSION


class SettingsV3(SettingsV2):
    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV3.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV3.STATIC_VERSION:
            super().migrate(data)

        try:
            if not any(interface["name"] == "uap0" for interface in data["interfaces"]):
                data["interfaces"].append(
                    Interface(name="uap0", domain_names=["blueos-hotspot"], advertise=["_http"], ip="ips[0]").dict()
                )
        except Exception as e:
            logger.error(f"unable to update SettingsV2 to SettingsV3: {e}")

        data["VERSION"] = SettingsV3.STATIC_VERSION


class SettingsV4(SettingsV3):
    vehicle_name: str = ""

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV4.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV4.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV4.STATIC_VERSION
