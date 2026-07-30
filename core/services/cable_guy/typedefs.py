from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, IPvAnyAddress, IPvAnyNetwork


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
    destination: IPvAnyNetwork
    gateway: Optional[IPvAnyAddress] = None
    priority: Optional[int] = None
    managed: bool = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return NotImplemented
        return self.destination == other.destination and self.gateway == other.gateway

    def __hash__(self) -> int:
        return hash(
            (
                self.destination,
                self.gateway,
            )
        )

    @property
    def is_default(self) -> bool:
        return self.destination.is_unspecified

    @property
    def is_multicast(self) -> bool:
        return self.destination.is_multicast


class NetworkInterfaceV1(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo] = None
    priority: Optional[int] = None

    def __hash__(self) -> int:
        return hash(self.name) + sum(hash(address) for address in self.addresses)


class NetworkInterface(NetworkInterfaceV1):
    routes: List[Route]


class NetworkInterfaceMetric(BaseModel):
    name: str
    index: int
    priority: int


class NetworkInterfaceMetricApi(BaseModel):
    name: str
    priority: int
