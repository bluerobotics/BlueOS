from enum import Enum
from typing import Any, Dict, Optional, Type

import validators
from pydantic import dataclasses, root_validator


class EndpointType(str, Enum):
    UDPServer = "udpin"
    UDPClient = "udpout"
    TCP = "tcp"
    Serial = "serial"
    File = "file"


@dataclasses.dataclass
class Endpoint:
    connection_type: str
    place: str
    argument: Optional[int] = None

    @root_validator
    @classmethod
    def is_mavlink_endpoint(cls: Type["Endpoint"], values: Any) -> Any:
        connection_type, place, argument = (values.get("connection_type"), values.get("place"), values.get("argument"))

        if connection_type in [EndpointType.UDPServer, EndpointType.UDPClient, EndpointType.TCP]:
            if not (validators.domain(place) or validators.ipv4(place) or validators.ipv6(place)):
                raise ValueError(f"Invalid network address: {place}")
            if not argument in range(1, 65536):
                raise ValueError(f"Ports must be in the range 1:65535. Received {argument}.")
            return values

        if connection_type == EndpointType.Serial.value:
            if not place.startswith("/") or place.endswith("/"):
                raise ValueError(f"Bad serial address: {place}. Make sure to use an absolute path.")
            if not argument in VALID_SERIAL_BAUDRATES:
                raise ValueError(f"Invalid serial baudrate: {argument}. Valid option are {VALID_SERIAL_BAUDRATES}.")
            return values

        if connection_type == EndpointType.File.value:
            if "/" in place:
                raise ValueError(f"Bad filename: {place}. Valid filenames do not contain '/' characters.")
            if argument is not None:
                raise ValueError(f"File endpoint should have no argument. Received {argument}.")
            return values

        raise ValueError(
            f"Invalid connection_type: {connection_type}. Valid types are: {[e.value for e in EndpointType]}."
        )

    def __str__(self) -> str:
        return ":".join([self.connection_type, self.place, str(self.argument)])

    def asdict(self) -> Dict[str, Any]:
        return {
            "connection_type": self.connection_type,
            "place": self.place,
            "argument": self.argument,
        }


VALID_SERIAL_BAUDRATES = [
    3000000,
    2000000,
    1000000,
    921600,
    570600,
    460800,
    257600,
    250000,
    230400,
    115200,
    57600,
    38400,
    19200,
    9600,
]
