#!/usr/bin/python

import asyncio
from enum import Enum
from typing import Dict, List, Tuple, Union

import pynmea2
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from loguru import logger
from pydantic import BaseModel, conint

from exceptions import UnsupportedSocketKind
from MavlinkNMEA import MavlinkGpsInput, parse_mavlink_from_sentence


class SocketKind(str, Enum):
    """Available server sockets"""

    UDP = "UDP"
    TCP = "TCP"


class NMEASocket(BaseModel):
    """NMEA server socket.
    Serializable model containing the necessary information (network and mavlink-wise) used to specify a socket."""

    kind: SocketKind
    port: conint(gt=1023, lt=65536)  # type: ignore
    component_id: conint(gt=25, lt=250)  # type: ignore

    def __str__(self) -> str:
        return f"{self.kind}:{self.port}"

    def __hash__(self) -> int:
        return hash(str(self))


class TcpNmeaProtocol(asyncio.Protocol):
    """Protocol class used to interface with Python's TCP Transport API."""

    def __init__(self, component_id: int) -> None:
        self._component_id = component_id

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Behavior when a new connection is stablished."""
        logger.debug(f"New TCP connection with {transport.get_extra_info('peername')}.")
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        """What happens when data is received from a client socket."""
        message = data.decode()
        logger.info(f"Message received for component {self._component_id}: {message}")
        mavlink_package = TrafficController.parse_mavlink_package(message)
        TrafficController.forward_message(mavlink_package, self._component_id)
        logger.info("Successfully forwarded mavlink coordinates package.")


class UdpNmeaProtocol(asyncio.DatagramProtocol):
    def __init__(self, component_id: int) -> None:
        self._component_id = component_id

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Behavior when a new connection is stablished."""
        logger.debug(f"New UDP connection with {transport.get_extra_info('peername')}.")
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """What happens when data is received from a client socket."""
        message = data.decode()
        logger.info(f"Message received for component {self._component_id}: {message}")
        mavlink_package = TrafficController.parse_mavlink_package(message)
        TrafficController.forward_message(mavlink_package, self._component_id)
        logger.info("Successfully forwarded mavlink coordinates package.")


class TrafficController:
    """Responsible for managing NMEA server sockets and traffic NMEA data between them and the Mavlink channel."""

    def __init__(self) -> None:
        self._socks: Dict[NMEASocket, Union[asyncio.AbstractServer, asyncio.BaseTransport]] = {}

    def get_socks(self) -> List[NMEASocket]:
        """Retrieve information about available server sockets."""
        return list(self._socks)

    async def add_sock(self, sock: NMEASocket) -> None:
        """Open a new network server socket and asynchronously wait for connections to arrive."""
        loop = asyncio.get_running_loop()
        server_socket: Union[asyncio.AbstractServer, asyncio.BaseTransport]
        if sock.kind == SocketKind.TCP:
            server_socket = await loop.create_server(lambda: TcpNmeaProtocol(sock.component_id), "0.0.0.0", sock.port)
        elif sock.kind == SocketKind.UDP:
            server_socket, _ = await loop.create_datagram_endpoint(
                lambda: UdpNmeaProtocol(sock.component_id), local_addr=("0.0.0.0", sock.port)
            )
        else:
            raise UnsupportedSocketKind(f"Got {sock.kind}. Expected one of: {[kind.value for kind in SocketKind]}.")
        self._socks[sock] = server_socket
        logger.debug(f"Added new sock: {sock}.")

    def remove_sock(self, sock: NMEASocket) -> None:
        """Remove existing socket."""
        server_socket = self._socks.pop(sock, None)
        if server_socket is None:
            raise ValueError(f"Socket {sock} does not exist.")
        server_socket.close()
        logger.debug(f"Removed sock. Socks now: {self.get_socks()}.")

    @staticmethod
    def parse_mavlink_package(nmea_msg: str) -> MavlinkGpsInput:
        """Transform NMEA message into proper Mavlink GPS_INPUT package."""
        nmea_sentence = pynmea2.parse(nmea_msg)
        return parse_mavlink_from_sentence(nmea_sentence)

    @staticmethod
    def forward_message(message: MavlinkGpsInput, component_id: int) -> None:
        """Forward Mavlink message package to Mavlink2Rest, on the specified component ID."""
        mavlink2rest = MavlinkMessenger()
        mavlink2rest.set_component_id(component_id)
        mavlink2rest.send_mavlink_message(message.dict())
