from enum import Enum
from typing import Dict

from pydantic import BaseModel


class Parameters(BaseModel):
    params: Dict[str, float]


class EndpointType(str, Enum):
    """Supported Mavlink endpoint types."""

    UDPServer = "udpin"
    UDPClient = "udpout"
    TCPServer = "tcpin"
    TCPClient = "tcpout"
    Serial = "serial"
