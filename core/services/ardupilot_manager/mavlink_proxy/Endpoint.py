from enum import Enum
from typing import Annotated, Any, Dict, Iterable, Optional, Type

import validators
from pydantic import StringConstraints, model_validator
from pydantic.dataclasses import dataclass
from pydantic_core import ArgsKwargs


class EndpointType(str, Enum):
    """Supported Mavlink endpoint types."""

    UDPServer = "udpin"
    UDPClient = "udpout"
    TCPServer = "tcpin"
    TCPClient = "tcpout"
    Serial = "serial"
    Zenoh = "zenoh"
    ZenohRaw = "zenohraw"


@dataclass
# pylint: disable=too-many-instance-attributes
class Endpoint:
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
    owner: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]

    connection_type: str
    place: str
    argument: Optional[int] = None

    persistent: Optional[bool] = False
    protected: Optional[bool] = False
    enabled: Optional[bool] = True
    overwrite_settings: Optional[bool] = False

    @model_validator(mode="before")
    @classmethod
    def is_mavlink_endpoint(cls: Type["Endpoint"], values: Any) -> Any:
        if isinstance(values, ArgsKwargs):
            values = dict(values.kwargs or {})

        connection_type, place, argument = (values.get("connection_type"), values.get("place"), values.get("argument"))

        if connection_type in [
            EndpointType.UDPServer,
            EndpointType.UDPClient,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
            EndpointType.Zenoh,
            EndpointType.ZenohRaw,
        ]:
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

        return values

    def is_supported(self) -> bool:
        return self.connection_type in {endpoint_type.value for endpoint_type in EndpointType}

    @staticmethod
    def filter_enabled(endpoints: Iterable["Endpoint"]) -> Iterable["Endpoint"]:
        return [endpoint for endpoint in endpoints if endpoint.enabled is True and endpoint.is_supported()]

    @staticmethod
    def from_raw(raw_endpoint: Any) -> Optional["Endpoint"]:
        """Build an endpoint from a saved record, returning None if the record is not an endpoint."""
        try:
            return Endpoint(**raw_endpoint)
        except Exception:
            return None

    def as_api_dict(self) -> Dict[str, Any]:
        data = self.as_dict()
        if not self.is_supported():
            data["enabled"] = False
        return data

    def __str__(self) -> str:
        return ":".join([self.connection_type, self.place, str(self.argument)])

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "owner": self.owner,
            "connection_type": self.connection_type,
            "place": self.place,
            "argument": self.argument,
            "persistent": self.persistent,
            "protected": self.protected,
            "enabled": self.enabled,
            "overwrite_settings": self.overwrite_settings,
        }

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
