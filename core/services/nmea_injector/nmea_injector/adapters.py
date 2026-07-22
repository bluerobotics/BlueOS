import asyncio
from typing import Dict, List, Tuple

import pynmea2
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from commonwealth.settings.manager import PydanticManager
from loguru import logger
from nmea_injector.commands import AddSock, SocketKind
from nmea_injector.exceptions import UnsupportedSocketKind
from nmea_injector.MavlinkNMEA import MavlinkGpsInput, parse_mavlink_from_sentence
from nmea_injector.ports import Closeable, MavlinkSink
from nmea_injector.settings import NmeaInjectorSettingsSpecV1, SettingsV1
from nmea_injector.views import SocksView


class MavlinkMessengerSink:
    """Driven adapter: one MavlinkMessenger per component_id."""

    def __init__(self) -> None:
        self._messengers: Dict[int, MavlinkMessenger] = {}

    def _messenger(self, component_id: int) -> MavlinkMessenger:
        messenger = self._messengers.get(component_id)
        if messenger is None:
            messenger = MavlinkMessenger()
            messenger.set_component_id(component_id)
            self._messengers[component_id] = messenger
        return messenger

    async def send_gps(self, component_id: int, message: MavlinkGpsInput) -> None:
        await self._messenger(component_id).send_mavlink_message(message.dict())


class _TcpNmeaProtocol(asyncio.Protocol):
    def __init__(self, component_id: int, sink: MavlinkSink) -> None:
        self._component_id = component_id
        self._sink = sink

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        logger.debug(f"New TCP connection with {transport.get_extra_info('peername')}.")
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        message = data.decode()
        logger.info(f"Message received for component {self._component_id}: {message}")
        mavlink_package = parse_mavlink_from_sentence(pynmea2.parse(message))
        asyncio.create_task(self._sink.send_gps(self._component_id, mavlink_package))
        logger.info("Successfully forwarded mavlink coordinates package.")


class _UdpNmeaProtocol(asyncio.DatagramProtocol):
    def __init__(self, component_id: int, sink: MavlinkSink) -> None:
        self._component_id = component_id
        self._sink = sink

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        logger.debug(f"New UDP connection with {transport.get_extra_info('peername')}.")
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        message = data.decode()
        logger.info(f"Message received for component {self._component_id}: {message}")
        mavlink_package = parse_mavlink_from_sentence(pynmea2.parse(message))
        asyncio.create_task(self._sink.send_gps(self._component_id, mavlink_package))
        logger.info("Successfully forwarded mavlink coordinates package.")


class AsyncioSockListener:
    def __init__(self, sink: MavlinkSink) -> None:
        self._sink = sink

    async def listen(self, kind: SocketKind | str, port: int, component_id: int) -> Closeable:
        loop = asyncio.get_running_loop()
        if kind == SocketKind.TCP:
            return await loop.create_server(lambda: _TcpNmeaProtocol(component_id, self._sink), "0.0.0.0", port)
        if kind == SocketKind.UDP:
            server_socket, _ = await loop.create_datagram_endpoint(
                lambda: _UdpNmeaProtocol(component_id, self._sink), local_addr=("0.0.0.0", port)
            )
            return server_socket
        raise UnsupportedSocketKind(f"Got {kind}. Expected one of: {[k.value for k in SocketKind]}.")


class PydanticSockSettingsStore:
    def __init__(self, manager: PydanticManager | None = None) -> None:
        self._manager = manager or PydanticManager("nmea-injector", SettingsV1)

    def load(self) -> List[AddSock]:
        self._manager.load()
        return [
            AddSock(kind=SocketKind(spec.kind), port=spec.port, component_id=spec.component_id)
            for spec in self._manager.settings.specs
        ]

    def save(self, view: SocksView) -> None:
        self._manager.settings.specs = [
            NmeaInjectorSettingsSpecV1(kind=sock.kind, port=sock.port, component_id=sock.component_id)
            for sock in view.socks
        ]
        self._manager.save()
