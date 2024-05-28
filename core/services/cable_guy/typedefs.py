from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class AddressMode(str, Enum):
    Client = "client"
    Server = "server"
    Unmanaged = "unmanaged"


class InterfaceAddress(BaseModel):
    ip: str
    mode: AddressMode


class InterfaceInfo(BaseModel):
    connected: bool
    number_of_disconnections: int
    priority: int


class NetworkInterface(BaseModel):
    name: str
    addresses: List[InterfaceAddress]
    info: Optional[InterfaceInfo]


class NetworkInterfaceMetric(BaseModel):
    name: str
    index: int
    priority: int


class NetworkInterfaceMetricApi(BaseModel):
    name: str
    priority: Optional[int]
