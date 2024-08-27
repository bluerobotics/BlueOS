from typing import Any, Dict, Iterable, Optional, Type

import validators
from pydantic import constr, root_validator
from pydantic.dataclasses import dataclass

from typedefs import EndpointType


@dataclass
# pylint: disable=too-many-instance-attributes
class Endpoint:
    name: constr(strip_whitespace=True, min_length=3, max_length=50)  # type: ignore
    owner: constr(strip_whitespace=True, min_length=3, max_length=50)  # type: ignore

    connection_type: str
    place: str
    argument: Optional[int] = None

    persistent: Optional[bool] = False
    protected: Optional[bool] = False
    enabled: Optional[bool] = True
    overwrite_settings: Optional[bool] = False

    @root_validator
    @classmethod
    def is_mavlink_endpoint(cls: Type["Endpoint"], values: Any) -> Any:
        connection_type, place, argument = (values.get("connection_type"), values.get("place"), values.get("argument"))

        if connection_type in [
            EndpointType.UDPServer,
            EndpointType.UDPClient,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
        ]:
            # pylint: disable-next=too-many-function-args
            if not (validators.domain(place) or validators.ipv4(place) or validators.ipv6(place)):
                raise ValueError(f"Invalid network address: {place}")
            if argument not in range(1, 65536):
                raise ValueError(f"Ports must be in the range 1:65535. Received {argument}.")
            return values

        if connection_type == EndpointType.Serial.value:
            if not place.startswith("/") or place.endswith("/"):
                raise ValueError(f"Bad serial address: {place}. Make sure to use an absolute path.")
            if argument not in VALID_SERIAL_BAUDRATES:
                raise ValueError(f"Invalid serial baudrate: {argument}. Valid option are {VALID_SERIAL_BAUDRATES}.")
            return values

        raise ValueError(
            f"Invalid connection_type: {connection_type}. Valid types are: {[e.value for e in EndpointType]}."
        )

    @staticmethod
    def filter_enabled(endpoints: Iterable["Endpoint"]) -> Iterable["Endpoint"]:
        return [endpoint for endpoint in endpoints if endpoint.enabled is True]

    def __str__(self) -> str:
        return ":".join([self.connection_type, self.place, str(self.argument)])

    def as_dict(self) -> Dict[str, Any]:
        return dict(filter(lambda field: field[0] != "__initialised__", self.__dict__.items()))

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            raise NotImplementedError
        return str(self) == str(other) and self.connection_type == other.connection_type and self.place == other.place


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
