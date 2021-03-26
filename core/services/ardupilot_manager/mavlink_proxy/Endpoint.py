from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union


class EndpointType(str, Enum):
    Undefined = "undefined"
    UDPServer = "udpin"
    UDPClient = "udpout"
    TCP = "tcp"
    Serial = "serial"
    File = "file"


@dataclass
class Endpoint:
    place: str
    argument: Optional[str]
    connType: EndpointType = EndpointType.Undefined

    def __init__(self, constructor: Union[str, Dict[str, str]] = "") -> None:
        if isinstance(constructor, dict):
            self.from_dict(constructor)
        else:
            self.from_str(constructor)

    def from_str(self, pattern: str) -> "Endpoint":
        args = pattern.split(":")
        if len(args) != 2 and len(args) != 3:
            raise RuntimeError("Wrong format for endpoint creation.")

        for item in EndpointType:
            if args[0] == item.value:
                self.connType = item
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

        for item in EndpointType:
            if pattern["connType"] == item.value:
                self.connType = item
                break
        else:
            self.connType = EndpointType.Undefined

        self.place = pattern["place"]
        self.argument = pattern["argument"] if pattern["argument"] else None

        return self

    def __str__(self) -> str:
        return ":".join([self.connType, self.place, self.argument if self.argument else ""])
