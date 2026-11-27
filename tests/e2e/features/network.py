from contextlib import AbstractContextManager
from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Protocol


class Router(Protocol):
    """The router the vehicle's ethernet is plugged into"""

    def without_dhcp_server(self) -> AbstractContextManager[None]:
        ...


@dataclass(frozen=True)
class Lease:
    ip: IPv4Address
    server: IPv4Address


class ClientPc(Protocol):
    """A PC plugged into the router next to the vehicle"""

    def connected(self) -> AbstractContextManager[Lease]:
        """Gets an address by dhcp, releases it on exit"""

    def get(self, url: str) -> str:
        ...
