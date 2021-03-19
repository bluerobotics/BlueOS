from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Union


class EndpointType(IntEnum):
    Undefined = 0
    UDPServer = 1
    UDPClient = 2
    TCP = 3
    Serial = 4
    File = 5


@dataclass
class Endpoint:
    place: str
    argument: Optional[str]
    connType: EndpointType = EndpointType.Undefined

    _connTypeMap = [
        (["udpin"], EndpointType.UDPServer),
        (["udp", "udpout"], EndpointType.UDPClient),
        (["tcp"], EndpointType.TCP),
        (["serial"], EndpointType.Serial),
        (["file"], EndpointType.File),
    ]

    def __init__(self, constructor: Union[str, Dict[str, str]] = "") -> None:
        if isinstance(constructor, dict):
            self.from_dict(constructor)
        else:
            self.from_str(constructor)

    def from_str(self, pattern: str) -> "Endpoint":
        args = pattern.split(":")
        if len(args) != 2 and len(args) != 3:
            raise RuntimeError("Wrong format for endpoint creation.")

        for stringType, endpointType in self._connTypeMap:
            if args[0] in stringType:
                self.connType = endpointType
                break
        else:
            self.connType = EndpointType.Undefined

        self.place = args[1]
        self.argument = args[2] if len(args) == 3 else None

        return self

    def from_dict(self, pattern: Dict[str, str]) -> "Endpoint":
        if not {"connType", "place"}.issubset(pattern.keys()):
            diff = {"connType", "place"}.difference(pattern.keys())
            raise RuntimeError(f"Wrong format for endpoint creation, missing the following: {diff}.")

        for stringType, endpointType in self._connTypeMap:
            if pattern["connType"] in stringType:
                self.connType = endpointType
                break
        else:
            self.connType = EndpointType.Undefined

        self.place = pattern["place"]
        self.argument = pattern["argument"] if pattern["argument"] else None

        return self

    def __str__(self) -> str:
        connTypeString = "Undefined"
        for stringType, endpointType in self._connTypeMap:
            if endpointType == self.connType:
                connTypeString = stringType[0]
                break

        return ":".join([connTypeString, self.place, self.argument if self.argument else ""])
