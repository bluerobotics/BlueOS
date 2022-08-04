from dataclasses import dataclass
from enum import IntEnum

from loguru import logger
from serial.tools.list_ports_linux import SysFS


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
        except Exception as _:
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
    port: SysFS
    driver: Optional["PingDriver"]  # type: ignore

    def __hash__(self) -> int:
        return hash(self.port.hwid)

    def __str__(self) -> str:
        return f"""{self.ping_type.name}
ID: {self.device_id}
FW: v{self.firmware_version_major}.{self.firmware_version_minor}.{self.firmware_version_patch}
port: {self.port.hwid}"""
