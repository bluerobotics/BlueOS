from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, Self


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    remove: Callable[[], None] = field(compare=False)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.remove()


class WifiScanner(Protocol):
    def scan(self) -> list[str]:
        ...


class WifiAccessPoints(Protocol):
    def create_access_point(self, ssid: str, channel: int, passphrase: str | None = None) -> AccessPoint:
        ...
