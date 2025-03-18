from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


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


class NetworkInterface(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo]
    priority: Optional[int]

    def __hash__(self) -> int:
        return hash(self.name) + sum(hash(address) for address in self.addresses)


class NetworkInterfaceMetric(BaseModel):
    name: str
    index: int
    priority: int


class NetworkInterfaceMetricApi(BaseModel):
    name: str
    priority: int
