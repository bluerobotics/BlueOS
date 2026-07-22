from bridges.serialhelper import Baudrate
from commands import AddBridge, RemoveBridge
from pydantic import BaseModel, conint


class BridgeRequest(BaseModel):
    """HTTP body for add/remove — mapped to commands at the boundary."""

    serial_path: str
    baud: Baudrate
    ip: str
    udp_target_port: conint(ge=0, lt=65536)  # type: ignore
    udp_listen_port: conint(ge=0, lt=65536)  # type: ignore

    def to_add(self) -> AddBridge:
        return AddBridge(
            serial_path=self.serial_path,
            baud=int(self.baud),
            ip=self.ip,
            udp_target_port=int(self.udp_target_port),
            udp_listen_port=int(self.udp_listen_port),
        )

    def to_remove(self) -> RemoveBridge:
        return RemoveBridge(
            serial_path=self.serial_path,
            baud=int(self.baud),
            ip=self.ip,
            udp_target_port=int(self.udp_target_port),
            udp_listen_port=int(self.udp_listen_port),
        )
