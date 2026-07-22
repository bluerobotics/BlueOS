from dataclasses import dataclass
from enum import Enum


class SocketKind(str, Enum):
    UDP = "UDP"
    TCP = "TCP"


@dataclass(frozen=True)
class AddSock:
    """Command: open a listener and persist it."""

    kind: SocketKind
    port: int
    component_id: int


@dataclass(frozen=True)
class RemoveSock:
    """Command: close a listener and drop it from settings."""

    kind: SocketKind
    port: int
    component_id: int
