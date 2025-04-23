from enum import Enum
from ipaddress import ip_network
from typing import List, Optional

from pydantic import BaseModel

# TODO: Replace this by `from pydantic import IPvAnyAddress, IPvAnyNetwork` once we update to pydantic v2
from typedefs_pydantic_network_shin import IPvAnyAddress, IPvAnyNetwork


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
    destination: str  # TODO: change this to IPvAnyNetwork from pydantic v2
    gateway: Optional[str] = None  # TODO: change this to IPvAnyAddress from pydantic v2
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

    # TODO: Remove this once we update self.destination type
    @property
    def destination_parsed(self) -> IPvAnyNetwork:
        return IPvAnyNetwork(self.destination)

    # TODO: Remove this once we update self.destination type
    @destination_parsed.setter
    def destination_parsed(self, ip: IPvAnyNetwork) -> None:
        self.destination = str(ip)

    # TODO: Remove this once we update self.next_hop type
    @property
    def next_hop_parsed(self) -> Optional[IPvAnyAddress]:
        if self.gateway is None:
            return None
        return IPvAnyAddress(self.gateway)

    # TODO: Remove this once we update self.next_hop type
    @next_hop_parsed.setter
    def next_hop_parsed(self, ip: Optional[IPvAnyAddress]) -> None:
        self.gateway = str(ip) if ip else None

    @property
    def is_default(self) -> bool:
        return ip_network(self.destination).is_unspecified

    @property
    def is_multicast(self) -> bool:
        return ip_network(self.destination).is_multicast


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
