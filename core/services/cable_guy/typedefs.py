from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class AddressMode(str, Enum):
    Client = "client"
    Server = "server"
    Unmanaged = "unmanaged"

    def __hash__(self) -> int:
        return hash(self.value)


class InterfaceAddress(BaseModel):
    ip: str
    mode: AddressMode

    def __hash__(self) -> int:
        return hash(self.ip) + hash(self.mode)


class InterfaceInfo(BaseModel):
    connected: bool
    number_of_disconnections: int
    priority: int


class NetworkInterface(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo]

    def __hash__(self) -> int:
        return hash(self.name) + sum(hash(address) for address in self.addresses)


class NetworkInterfaceMetric(BaseModel):
    name: str
    index: int
    priority: int


class NetworkInterfaceMetricApi(BaseModel):
    name: str
    priority: Optional[int]
