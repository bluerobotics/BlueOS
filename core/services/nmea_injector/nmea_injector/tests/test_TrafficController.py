import asyncio
import socket
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import pytest
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from nmeasim.simulator import Simulator

from nmea_injector.TrafficController import NMEASocket, SocketKind, TrafficController

# Global test parameters
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 27000
COMPONENT_ID = 220
SERVER_ADDR = (SERVER_HOST, SERVER_PORT)


@pytest.mark.asyncio
async def test_endpoint_management_pipeline() -> None:
    for sock_kind in [SocketKind.UDP, SocketKind.TCP]:
        controller = TrafficController()
        test_sock = NMEASocket(kind=sock_kind, port=SERVER_PORT, component_id=COMPONENT_ID)

        for _ in range(10):
            try:
                await controller.add_sock(test_sock)
                break
            except OSError:
                # Port already in use, wait
                await asyncio.sleep(1)

        available_socks = controller.get_socks()
        assert len(available_socks) == 1
        controller._settings_manager.load()
        assert test_sock.to_settings_spec() in controller._settings_manager.settings.specs

        assert available_socks[0].kind == test_sock.kind
        assert available_socks[0].port == test_sock.port
        assert available_socks[0].component_id == test_sock.component_id

        controller.remove_sock(test_sock)
        available_socks = controller.get_socks()
        assert len(available_socks) == 0
        controller._settings_manager.load()
        assert test_sock.to_settings_spec() not in controller._settings_manager.settings.specs


@pytest.mark.asyncio
async def test_endpoint_communication(mocker: MagicMock) -> None:
    @mock.create_autospec
    # pylint: disable=unused-argument
    def mock_send_mavlink_message(self: MavlinkMessenger, message: Dict[str, Any]) -> None:
        pass

    mocker.patch("nmea_injector.TrafficController.MavlinkMessenger.send_mavlink_message", mock_send_mavlink_message)

    for sock_kind in [SocketKind.UDP, SocketKind.TCP]:
        controller = TrafficController()
        test_sock = NMEASocket(kind=sock_kind, port=SERVER_PORT, component_id=COMPONENT_ID)
        for _ in range(10):
            try:
                await controller.add_sock(test_sock)
                break
            except OSError:
                # Port already in use, wait
                await asyncio.sleep(1)

        sim = Simulator()
        with sim.lock:
            sim.gps.output = ("GGA",)
            sim.gps.lat = 12345

        for raw_sentence in list(sim.get_output(3)):
            test_msg = raw_sentence
            bytes_to_send = str.encode(test_msg)

            if sock_kind == SocketKind.UDP:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.sendto(bytes_to_send, SERVER_ADDR)

            if sock_kind == SocketKind.TCP:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(SERVER_ADDR)
                sock.sendall(bytes_to_send)
                sock.shutdown(socket.SHUT_RD)
                sock.close()

            # Wait to make sure async protocol transfer has been completed
            await asyncio.sleep(0.1)
            original_msg = TrafficController.parse_mavlink_package(raw_sentence)
            _, forwarded_msg = mock_send_mavlink_message.call_args[0]
            assert original_msg == forwarded_msg
