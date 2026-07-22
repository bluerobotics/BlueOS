from nmea_injector.commands import AddSock, RemoveSock, SocketKind
from pydantic import BaseModel, conint


class SockRequest(BaseModel):
    """HTTP body for add/remove — mapped to commands at the boundary."""

    kind: SocketKind
    port: conint(gt=1023, lt=65536)  # type: ignore
    component_id: conint(gt=25, lt=250)  # type: ignore

    def to_add(self) -> AddSock:
        return AddSock(kind=self.kind, port=int(self.port), component_id=int(self.component_id))

    def to_remove(self) -> RemoveSock:
        return RemoveSock(kind=self.kind, port=int(self.port), component_id=int(self.component_id))
