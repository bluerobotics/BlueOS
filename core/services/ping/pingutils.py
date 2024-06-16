import socket
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import psutil
from loguru import logger
from serial.tools.list_ports_linux import SysFS

from exceptions import InvalidDeviceDescriptor


class PingType(IntEnum):
    UNKNOWN = 0
    # These match the definitions in the ping firmwares
    PING1D = 1
    PING360 = 2

    # TODO: This should be fixed in ping-python documentation
    def __str__(self) -> str:
        names = {
            0: "UNKNOWN",
            1: "Ping1D",
            2: "Ping360",
        }
        try:
            return names[self.value]
        except Exception:
            logger.error(f"Wrong ping type: {self.value}")
            return "ErrorType"


# pylint: disable=too-many-instance-attributes
@dataclass
class PingDeviceDescriptor:
    ping_type: PingType
    device_id: int
    device_model: int
    device_revision: int
    firmware_version_major: int
    firmware_version_minor: int
    firmware_version_patch: int
    port: Optional[SysFS]
    ethernet_discovery_info: Optional[str]
    # Driver instances should not differentiate devices, so don't compare them
    driver: Optional["PingDriver"] = field(default=None, compare=False)  # type: ignore

    def __post_init__(self) -> None:
        if not (self.port or self.ethernet_discovery_info):
            raise InvalidDeviceDescriptor("PingDeviceDescriptor needs either port or ethernet_info")

    def get_hw_or_eth_info(self) -> str:
        if self.port:
            return str(self.port.device_path)
        return str(self.ethernet_discovery_info)

    def __hash__(self) -> int:
        return hash(self.get_hw_or_eth_info())

    def __str__(self) -> str:
        return f"""{self.ping_type.name}
ID: {self.device_id}
FW: v{self.firmware_version_major}.{self.firmware_version_minor}.{self.firmware_version_patch}
port: {self.get_hw_or_eth_info()}"""


def udp_port_is_in_use(port: int) -> bool:
    return any(
        conn.laddr.port == port and conn.type == socket.SocketKind.SOCK_DGRAM for conn in psutil.net_connections()
    )
