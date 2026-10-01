import glob
import pathlib
import subprocess
import time
from typing import Any, Callable, List, Optional, Set
from unittest.mock import Mock

import psutil
import pytest
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from loguru import logger
from typedefs import Platform

BABEL = "/dev/serial/by-id/usb-CUAV_CUAV_CAN_Babel-if00"
STTY = ["stty", "-F", BABEL, "3000000", "raw", "-echo", "-hupcl", "clocal"]
LDATTACH = ["ldattach", "17", BABEL]
OPEN_CHANNEL = ["open-channel", BABEL]
BITRATE_ARGUMENTS = ["type", "can", "bitrate", "1000000", "restart-ms", "100", "loopback", "off"]


def make_board() -> LinuxFlightController:
    return LinuxFlightController(name="Test", platform=Platform.Navigator)


def fake_sysfs(
    monkeypatch: pytest.MonkeyPatch,
    interfaces: List[str],
    hardware: Set[str],
    babel: bool = False,
    processes: Optional[List[Mock]] = None,
) -> None:
    monkeypatch.setattr(LinuxFlightController, "can_interfaces", lambda _self: sorted(interfaces))
    monkeypatch.setattr(glob, "glob", lambda _pattern: [BABEL] if babel else [])
    existing = {f"/sys/class/net/{name}/device" for name in hardware}
    monkeypatch.setattr(pathlib.Path, "exists", lambda path: str(path) in existing)
    monkeypatch.setattr(psutil, "process_iter", lambda _attributes: processes or [])


def record_ip_calls(
    monkeypatch: pytest.MonkeyPatch,
    fail: bool = False,
    ldattach_returncode: int = 0,
    on_call: Optional[Callable[[List[str]], None]] = None,
) -> List[List[str]]:
    calls: List[List[str]] = []

    def fake_run(arguments: List[str], **_kwargs: Any) -> "subprocess.CompletedProcess[str]":
        calls.append(arguments)
        if fail:
            raise subprocess.CalledProcessError(1, arguments)
        if on_call:
            on_call(arguments)
        if arguments[0] != "ldattach":
            return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(arguments, ldattach_returncode, stdout="", stderr="cannot open device")

    def fake_open_channel(_self: LinuxFlightController, port: str) -> None:
        calls.append(["open-channel", port])

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(LinuxFlightController, "open_babel_channel", fake_open_channel)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return calls


def test_can_interfaces_lists_every_can_link_type(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    for name, link_type in {"can0": "280", "vcan0": "280", "eth0": "1", "wlan0": "801"}.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "type").write_text(f"{link_type}\n")
    # /sys/class/net also holds plain files, such as bonding_masters
    (tmp_path / "bonding_masters").write_text("")
    monkeypatch.setattr(LinuxFlightController, "NET_PATH", tmp_path)

    assert make_board().can_interfaces() == ["can0", "vcan0"]


def test_setup_can_skips_missing_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=[], hardware=set())
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    assert not calls


def test_setup_can_configures_every_hardware_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["can0", "can1"], hardware={"can0", "can1"})
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    # A stale loopback mode has to be cleared, and a real controller has to recover from bus-off on its own.
    # Neither applies to slcan, which has no loopback mode and rejects restart-ms.
    assert calls == [
        ["ip", "link", "set", "can0", "down"],
        ["ip", "link", "set", "can0", "up", *BITRATE_ARGUMENTS],
        ["ip", "link", "set", "can1", "down"],
        ["ip", "link", "set", "can1", "up", *BITRATE_ARGUMENTS],
    ]


def test_setup_can_failure_does_not_block_autopilot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["can0"], hardware={"can0"})
    record_ip_calls(monkeypatch, fail=True)

    make_board().setup_can()


def test_setup_can_unreadable_sysfs_does_not_block_autopilot(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(_self: LinuxFlightController) -> List[str]:
        raise PermissionError("/sys/class/net")

    monkeypatch.setattr(LinuxFlightController, "can_interfaces", unreadable)
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    assert not calls


def test_setup_can_attaches_babel_on_a_pre_6_0_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    interfaces: List[str] = []
    fake_sysfs(monkeypatch, interfaces, hardware=set(), babel=True)

    def kernel_names_slcan(arguments: List[str]) -> None:
        if arguments[0] == "ldattach":
            interfaces.append("slcan0")

    calls = record_ip_calls(monkeypatch, on_call=kernel_names_slcan)

    make_board().setup_can()

    assert calls == [
        STTY,
        OPEN_CHANNEL,
        LDATTACH,
        ["ip", "link", "set", "slcan0", "name", "can0"],
        ["ip", "link", "set", "can0", "up"],
    ]


def test_setup_can_reattaches_a_babel_left_by_an_earlier_start(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every start reattaches, so a channel an earlier start left open at another bitrate is closed and set to 1 Mbit
    interfaces = ["can0", "can1"]
    live = Mock(info={"cmdline": ["ldattach", "17", BABEL]})
    live.kill.side_effect = lambda: interfaces.remove("can1")
    fake_sysfs(monkeypatch, interfaces, hardware={"can0"}, babel=True, processes=[live])

    def kernel_names_slcan(arguments: List[str]) -> None:
        if arguments[0] == "ldattach":
            interfaces.append("can1")

    calls = record_ip_calls(monkeypatch, on_call=kernel_names_slcan)

    make_board().setup_can()

    live.kill.assert_called_once()
    # The killed attach has to be gone before the new interface is named, or this would be can2 and ArduPilot would
    # open a port that was never configured
    assert calls == [
        STTY,
        OPEN_CHANNEL,
        LDATTACH,
        ["ip", "link", "set", "can0", "down"],
        ["ip", "link", "set", "can0", "up", *BITRATE_ARGUMENTS],
        ["ip", "link", "set", "can1", "up"],
    ]


def test_open_babel_channel_closes_before_setting_the_bitrate(monkeypatch: pytest.MonkeyPatch) -> None:
    # SLCAN only takes a bitrate while the channel is closed, so writing C, S8 and O in one go leaves the bus at its
    # previous rate: the interface comes up and counts frames, and nothing on the wire is ever decoded
    events: List[str] = []
    port = Mock()
    port.__enter__ = Mock(return_value=port)
    port.__exit__ = Mock(return_value=False)
    port.write.side_effect = lambda data: events.append(data.decode())
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: port)
    monkeypatch.setattr(time, "sleep", lambda _seconds: events.append("settle"))

    make_board().open_babel_channel(BABEL)

    assert events == ["C\r", "settle", "S8\r", "settle", "O\r", "settle"]


def test_slcan_interfaces_ignores_a_virtual_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    # A vcan has no parent device either, and mistaking one for the Babel's own netdev would stall the detach
    fake_sysfs(monkeypatch, interfaces=["can0", "can1", "vcan0"], hardware={"can0"})

    assert make_board().slcan_interfaces() == ["can1"]


def test_setup_can_kills_ldattach_left_by_an_unplugged_babel(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = Mock(info={"cmdline": ["ldattach", "17", BABEL]})
    unrelated = Mock(info={"cmdline": ["ldattach", "PPP", "/dev/ttyS0"]})
    unreadable = Mock(info={"cmdline": None})
    fake_sysfs(monkeypatch, interfaces=[], hardware=set(), babel=True, processes=[stale, unrelated, unreadable])
    record_ip_calls(monkeypatch, ldattach_returncode=1)

    make_board().setup_can()

    stale.kill.assert_called_once()
    unrelated.kill.assert_not_called()
    unreadable.kill.assert_not_called()


def test_setup_can_attaches_babel_next_to_a_usb_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    # A gs_usb adapter present at boot takes can0, which must not stop the Babel from attaching as can1
    interfaces = ["can0"]
    fake_sysfs(monkeypatch, interfaces, hardware={"can0"}, babel=True)

    def kernel_names_slcan(arguments: List[str]) -> None:
        if arguments[0] == "ldattach":
            interfaces.append("can1")

    calls = record_ip_calls(monkeypatch, on_call=kernel_names_slcan)

    make_board().setup_can()

    assert calls == [
        STTY,
        OPEN_CHANNEL,
        LDATTACH,
        ["ip", "link", "set", "can0", "down"],
        ["ip", "link", "set", "can0", "up", *BITRATE_ARGUMENTS],
        ["ip", "link", "set", "can1", "up"],
    ]


def test_setup_can_attaches_babel_next_to_a_virtual_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    # A virtual bus gets brought up, but never a bitrate, since it has no parent device to take one
    interfaces = ["vcan0"]
    fake_sysfs(monkeypatch, interfaces, hardware=set(), babel=True)

    def kernel_names_slcan(arguments: List[str]) -> None:
        if arguments[0] == "ldattach":
            interfaces.append("can0")

    calls = record_ip_calls(monkeypatch, on_call=kernel_names_slcan)

    make_board().setup_can()

    assert calls == [
        STTY,
        OPEN_CHANNEL,
        LDATTACH,
        ["ip", "link", "set", "can0", "up"],
        ["ip", "link", "set", "vcan0", "up"],
    ]


def test_setup_can_reports_why_ldattach_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=[], hardware=set(), babel=True)
    calls = record_ip_calls(monkeypatch, ldattach_returncode=1)
    warnings: List[str] = []
    handler = logger.add(warnings.append, level="WARNING")

    try:
        make_board().setup_can()
    finally:
        logger.remove(handler)

    # Without the exit-code check this instead blames the missing interface
    assert "cannot open device" in "".join(warnings)
    assert calls == [STTY, OPEN_CHANNEL, LDATTACH]
