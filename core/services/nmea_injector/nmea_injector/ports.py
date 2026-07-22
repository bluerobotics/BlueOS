from typing import List, Protocol

from nmea_injector.commands import AddSock, SocketKind
from nmea_injector.MavlinkNMEA import MavlinkGpsInput
from nmea_injector.views import SocksView


class Closeable(Protocol):
    def close(self) -> None:
        ...


class SockListener(Protocol):
    async def listen(self, kind: SocketKind | str, port: int, component_id: int) -> Closeable:
        ...


class MavlinkSink(Protocol):
    async def send_gps(self, component_id: int, message: MavlinkGpsInput) -> None:
        ...


class SockSettingsStore(Protocol):
    def load(self) -> List[AddSock]:
        ...

    def save(self, view: SocksView) -> None:
        ...
