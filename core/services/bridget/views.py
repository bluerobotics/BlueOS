from dataclasses import dataclass
from typing import Tuple

from pydantic import BaseModel


class BridgeSummary(BaseModel):
    """Read-model DTO returned by queries — no write/settings/Bridge methods."""

    serial_path: str
    baud: int
    ip: str
    udp_target_port: int
    udp_listen_port: int

    class Config:
        frozen = True


@dataclass(frozen=True)
class BridgesView:
    """Immutable read model published after successful writes."""

    bridges: Tuple[BridgeSummary, ...]
