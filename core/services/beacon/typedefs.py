from enum import Enum

from pydantic import BaseModel


class InterfaceType(str, Enum):
    WIRED = "WIRED"
    WIFI = "WIFI"
    HOTSPOT = "HOTSPOT"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def guess_from_name(name: str) -> "InterfaceType":
        if name.startswith("wl"):
            return InterfaceType.WIFI
        if name.startswith("uap"):
            return InterfaceType.HOTSPOT
        if name.startswith("en"):
            return InterfaceType.WIRED
        if name.startswith("eth"):
            return InterfaceType.WIRED
        return InterfaceType.UNKNOWN


class MdnsEntry(BaseModel):
    ip: str
    hostname: str
    fullname: str
    interface: str
    interface_type: InterfaceType
    service_type: str


class IpInfo(BaseModel):
    client_ip: str
    interface_ip: str
