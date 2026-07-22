#!/usr/bin/python

from typing import Any, Dict, List

from commonwealth.service.service import EventHandler, ReadModelUpdated, ServiceState
from loguru import logger
from nmea_injector.commands import AddSock, RemoveSock, SocketKind
from nmea_injector.ports import Closeable, SockListener, SockSettingsStore
from nmea_injector.views import SockSummary, SocksView
from pydantic import BaseModel


class NMEASocket(BaseModel):
    """Write-model identity for a live listener (map key)."""

    kind: SocketKind
    port: int
    component_id: int

    def __str__(self) -> str:
        return f"{self.kind}:{self.port}"

    def __hash__(self) -> int:
        return hash(str(self))

    @staticmethod
    def from_command(cmd: AddSock | RemoveSock) -> "NMEASocket":
        return NMEASocket(kind=cmd.kind, port=cmd.port, component_id=cmd.component_id)

    def to_summary(self) -> SockSummary:
        return SockSummary(kind=self.kind, port=self.port, component_id=self.component_id)


class TrafficController(ServiceState):
    """Write model: live listeners. Settings persist via ReadModelUpdated subscriber."""

    def __init__(self, settings: SockSettingsStore, listener: SockListener) -> None:
        super().__init__()
        self._socks: Dict[NMEASocket, Closeable] = {}
        self._settings = settings
        self._listener = listener

    def subscribers(self) -> list[EventHandler]:
        return [self._persist_settings]

    def snapshot(self) -> SocksView:
        return SocksView(socks=tuple(sock.to_summary() for sock in self._socks))

    def _persist_settings(self, event: Any) -> None:
        if isinstance(event, ReadModelUpdated) and isinstance(event.model, SocksView):
            self._settings.save(event.model)

    def settings_socks(self) -> List[NMEASocket]:
        return [NMEASocket.from_command(cmd) for cmd in self._settings.load()]

    def get_socks(self) -> List[NMEASocket]:
        return list(self._socks)

    def has_sock(self, sock: NMEASocket) -> bool:
        return sock in self._socks

    async def listen(self, sock: NMEASocket) -> Closeable:
        """Open a listener via the SockListener port (safe outside write())."""
        return await self._listener.listen(sock.kind, int(sock.port), int(sock.component_id))

    def apply_add(self, cmd: AddSock, server_socket: Closeable, *, emit: bool = True) -> None:
        sock = NMEASocket.from_command(cmd)
        if sock in self._socks:
            server_socket.close()
            raise ValueError(f"Socket {sock} already exists.")
        self._socks[sock] = server_socket
        logger.debug(f"Added new sock: {sock}.")
        if emit:
            self.publish_read_model()

    def apply_remove(self, cmd: RemoveSock, *, emit: bool = True) -> None:
        sock = NMEASocket.from_command(cmd)
        server_socket = self._socks.pop(sock, None)
        if server_socket is None:
            raise ValueError(f"Socket {sock} does not exist.")
        server_socket.close()
        logger.debug(f"Removed sock. Socks now: {self.get_socks()}.")
        if emit:
            self.publish_read_model()

    async def add_sock(self, sock: NMEASocket) -> None:
        """Test/helper path: open and apply AddSock without Service.write()."""
        self.apply_add(
            AddSock(kind=sock.kind, port=sock.port, component_id=sock.component_id),
            await self.listen(sock),
            emit=False,
        )

    def remove_sock(self, sock: NMEASocket) -> None:
        """Test/helper path: apply RemoveSock without Service.write()."""
        self.apply_remove(
            RemoveSock(kind=sock.kind, port=sock.port, component_id=sock.component_id),
            emit=False,
        )

    def __del__(self) -> None:
        for server_socket in list(self._socks.values()):
            try:
                server_socket.close()
            except Exception:
                # GC may run after the asyncio loop is already closed.
                pass
        self._socks.clear()
