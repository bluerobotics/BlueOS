from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    channel: int
    remove: Callable[[], None] = field(compare=False)


class WifiScanner(Protocol):
    def scan(self) -> list[str]:
        ...


class WifiAccessPoints(Protocol):
    def create_access_point(self, ssid: str, channel: int, passphrase: str | None = None) -> AccessPoint:
        ...
