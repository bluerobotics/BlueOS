import time
from typing import Any, Dict, List, Optional

import pytest
import serial
from flight_controller_detector.bootloader.px4_bootloader import (
    PX4BootLoader,
    PX4BootLoaderCommand,
    PX4BootLoaderDeviceInfo,
    PX4BootLoaderProtocol,
)
from flight_controller_detector.Detector import Detector

IN_SYNC_OK = bytes([PX4BootLoaderProtocol.INSYNC, PX4BootLoaderProtocol.OK])
BOOT_COMMAND = bytes([PX4BootLoaderCommand.BOOT, PX4BootLoaderProtocol.EOC])


class FakeBootloaderPort:
    """Answers like an ArduPilot bootloader, or with garbage if it is not in sync."""

    def __init__(self, device_info: Optional[Dict[int, int]] = None, in_sync: bool = True) -> None:
        self.device_info = device_info or {
            PX4BootLoaderDeviceInfo.BL_REV: 5,
            PX4BootLoaderDeviceInfo.BOARD_ID: 140,
            PX4BootLoaderDeviceInfo.FLASH_SIZE: 2_000_000,
        }
        self.in_sync = in_sync
        self.rx = bytearray()
        self.written: List[bytes] = []

    def __call__(self, *_args: Any, **_kwargs: Any) -> "FakeBootloaderPort":
        return self

    def __enter__(self) -> "FakeBootloaderPort":
        return self

    def __exit__(self, *_args: Any) -> None:
        pass

    def write(self, data: bytes) -> int:
        data = bytes(data)
        self.written.append(data)
        if not self.in_sync:
            self.rx += b"\x00\x00"
        elif data[0] == PX4BootLoaderCommand.GET_SYNC:
            self.rx += IN_SYNC_OK
        elif data[0] == PX4BootLoaderCommand.GET_DEVICE:
            self.rx += self.device_info[data[1]].to_bytes(4, "little") + IN_SYNC_OK
        return len(data)

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def read(self, size: int) -> bytes:
        data = bytes(self.rx[:size])
        del self.rx[:size]
        return data

    def read_all(self) -> bytes:
        return self.read(len(self.rx))

    def flush(self) -> None:
        pass


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def test_board_info_is_parsed() -> None:
    port = FakeBootloaderPort()
    info = PX4BootLoader(port).get_board_info()  # type: ignore[arg-type]
    assert (info.board_id, info.boot_loader_version, info.flash_size) == (140, 5, 2_000_000)
    assert BOOT_COMMAND not in port.written


def test_unsupported_bootloader_version_raises() -> None:
    port = FakeBootloaderPort({PX4BootLoaderDeviceInfo.BL_REV: 1})
    with pytest.raises(ValueError):
        PX4BootLoader(port).get_board_info()  # type: ignore[arg-type]


def test_sync_failure_raises() -> None:
    with pytest.raises(RuntimeError):
        PX4BootLoader(FakeBootloaderPort(in_sync=False)).get_board_info()  # type: ignore[arg-type]


def test_detector_boots_board_after_reading_info(monkeypatch: pytest.MonkeyPatch) -> None:
    port = FakeBootloaderPort()
    monkeypatch.setattr(serial, "Serial", port)
    assert Detector._ask_bootloader_for_board_id_sync("/dev/ttyACM0") == 140
    assert port.written[-1] == BOOT_COMMAND


@pytest.mark.parametrize(
    "port",
    [FakeBootloaderPort(in_sync=False), FakeBootloaderPort({PX4BootLoaderDeviceInfo.BL_REV: 1})],
    ids=["sync-failure", "unsupported-version"],
)
def test_detector_boots_board_and_survives_probe_failure(
    monkeypatch: pytest.MonkeyPatch, port: FakeBootloaderPort
) -> None:
    monkeypatch.setattr(serial, "Serial", port)
    assert Detector._ask_bootloader_for_board_id_sync("/dev/ttyACM0") is None
    assert port.written[-1] == BOOT_COMMAND


def test_detector_survives_port_open_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def busy_port(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("Device or resource busy")

    monkeypatch.setattr(serial, "Serial", busy_port)
    assert Detector._ask_bootloader_for_board_id_sync("/dev/ttyACM0") is None
