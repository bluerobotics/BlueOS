import ipaddress
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, validator


class Serial(BaseModel):
    """Simplified representation of linux serial port configurations,
    gets transformed into command line arguments such as
    --serial1 /dev/ttyS0
    --serial3 /dev/ttyAMA1
    --serial4 /dev/ttyAMA2
    --serial5 /dev/ttyAMA3
    """

    port: str
    endpoint: str

    @validator("port")
    @classmethod
    def valid_letter(cls: Any, value: str) -> str:
        if value in "BCDEFGH" and len(value) == 1:
            return value
        raise ValueError(f"Invalid serial port: {value}. These must be between B and H. A is reserved.")

    @validator("endpoint")
    @classmethod
    def valid_endpoint(cls: Any, value: str) -> str:
        if Path(value).exists():
            return value
        if re.compile(r"tcp:\d*:wait$").match(value):
            return value
        matches = re.compile(r"(tcpclient|udp|tcpin|udpin):(?P<ip>(\d*\.){3}\d+):(?P<port>\d*)$").match(value)
        if matches:
            ipaddress.ip_address(matches.group("ip"))
            if 0 <= int(matches.group("port")) <= 65535:
                return value
        raise ValueError(f"Invalid endpoint configuration: {value}")

    def __hash__(self) -> int:  # make hashable BaseModel subclass
        return hash(self.port + self.endpoint)
