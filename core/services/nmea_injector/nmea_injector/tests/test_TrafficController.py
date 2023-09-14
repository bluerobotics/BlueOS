import asyncio
import json
import socket
from typing import Generator, Optional
from unittest.mock import AsyncMock

import pytest
from nmeasim.simulator import Simulator
from pyfakefs.fake_filesystem import FakeFilesystem
from pyfakefs.fake_filesystem_unittest import Patcher

from nmea_injector.TrafficController import NMEASocket, SocketKind, TrafficController

# Global test parameters
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 27000
COMPONENT_ID = 220
SERVER_ADDR = (SERVER_HOST, SERVER_PORT)

# pyfakefs fixture
@pytest.fixture
def fs() -> Generator[Optional[FakeFilesystem], None, None]:
    patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


@pytest.mark.asyncio
async def test_endpoint_management_pipeline(fs: FakeFilesystem) -> None:
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
async def test_endpoint_communication(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send_mavlink_message = AsyncMock()

    monkeypatch.setattr(
        "nmea_injector.TrafficController.MavlinkMessenger.send_mavlink_message", mock_send_mavlink_message
    )

    for sock_kind in [SocketKind.UDP, SocketKind.TCP]:
        controller: Optional[TrafficController] = None
        for _ in range(10):
            try:
                controller = TrafficController()
                break
            except json.decoder.JSONDecodeError:
                await asyncio.sleep(1)
        if not controller:
            raise RuntimeError("Could not create controller.")
        test_sock = NMEASocket(kind=sock_kind, port=SERVER_PORT, component_id=COMPONENT_ID)
        for _ in range(10):
            try:
                await controller.add_sock(test_sock)
                break
            except OSError:
                # Port already in use, wait
                await asyncio.sleep(1)
        if controller.get_socks() != [test_sock]:
            raise RuntimeError("Could not add sock to controller.")

        sim = Simulator()
        with sim.lock:
            sim.gps.output = ("GGA",)
            sim.gps.lat = 12345

        for raw_sentence in list(sim.get_output(3)):
            test_msg = raw_sentence
            bytes_to_send = str.encode(test_msg)

            if sock_kind == SocketKind.UDP:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
            args, _ = mock_send_mavlink_message.call_args
            forwarded_msg = args[0]
            assert original_msg == forwarded_msg
