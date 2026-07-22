from dataclasses import dataclass
from typing import Tuple

from nmea_injector.commands import SocketKind
from pydantic import BaseModel


class SockSummary(BaseModel):
    """Read-model DTO returned by queries — no write/settings/listener methods."""

    kind: SocketKind
    port: int
    component_id: int

    class Config:
        frozen = True


@dataclass(frozen=True)
class SocksView:
    """Immutable read model published after successful writes."""

    socks: Tuple[SockSummary, ...]
