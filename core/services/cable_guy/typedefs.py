from enum import Enum
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from typing import List, Optional, Union

from pydantic import BaseModel

IPAddress = Union[IPv4Address, IPv6Address]
IPNetwork = Union[IPv4Network, IPv6Network]
IPInterface = Union[IPv4Interface, IPv6Interface]


class AddressMode(str, Enum):
    Client = "client"
    BackupServer = "backup_server"
    Server = "server"
    Unmanaged = "unmanaged"

    def __hash__(self) -> int:
        return hash(self.value)


class InterfaceAddress(BaseModel):
    ip: str
    mode: AddressMode

    def __hash__(self) -> int:
        if self.mode == AddressMode.Client:
            # we dont support multiple client ips. they will all be considered the same
            return hash(self.mode)
        return hash(self.mode) + hash(self.ip)


class InterfaceInfo(BaseModel):
    connected: bool
    number_of_disconnections: int
    priority: int


class Route(BaseModel):
    destination: IPNetwork
    next_hop: Optional[IPAddress]
    metric: Optional[int]
    default: bool
    enabled: bool


class NetworkInterface(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo] = None
    priority: Optional[int] = None
    routes: List[Route]

    def __hash__(self) -> int:
        return hash(self.name) + sum(hash(address) for address in self.addresses)


class NetworkInterfaceMetric(BaseModel):
    name: str
    index: int
    priority: int


class NetworkInterfaceMetricApi(BaseModel):
    name: str
    priority: int
