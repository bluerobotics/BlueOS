from typing import List, Protocol

from commands import AddBridge
from views import BridgesView


class LiveBridge(Protocol):
    def stop(self) -> None:
        ...


class BridgeRuntime(Protocol):
    # pylint: disable-next=too-many-arguments
    def open(
        self,
        serial_path: str,
        baud: int,
        ip: str,
        udp_target_port: int,
        udp_listen_port: int,
    ) -> LiveBridge:
        ...


class BridgeSettingsStore(Protocol):
    def load(self) -> List[AddBridge]:
        ...

    def save(self, view: BridgesView) -> None:
        ...


class SerialCatalog(Protocol):
    def list_ports(self) -> List[str]:
        ...
