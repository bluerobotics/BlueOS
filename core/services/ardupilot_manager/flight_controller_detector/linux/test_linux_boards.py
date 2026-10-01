import glob
import pathlib
import subprocess
from typing import Any, Callable, List, Optional, Set
from unittest.mock import Mock

import psutil
import pytest
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from loguru import logger
from typedefs import Platform

BABEL = "/dev/serial/by-id/usb-CUAV_CUAV_CAN_Babel-if00"
STTY = ["stty", "-F", BABEL, "3000000", "raw", "-echo", "-hupcl", "clocal"]
LDATTACH = ["ldattach", "-c", "C\rS8\rO\r", "17", BABEL]
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

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


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
        LDATTACH,
        ["ip", "link", "set", "slcan0", "name", "can0"],
        ["ip", "link", "set", "can0", "up"],
    ]


def test_setup_can_renames_slcan_left_by_an_earlier_start(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["slcan0"], hardware=set(), babel=True)
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    # Attaching again would kill the ldattach that still owns slcan0
    assert calls == [
        ["ip", "link", "set", "slcan0", "name", "can0"],
        ["ip", "link", "set", "can0", "up"],
    ]


def test_setup_can_kills_ldattach_left_by_an_unplugged_babel(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = Mock(info={"cmdline": ["ldattach", "-c", "C\nS8\nO\n", "17", BABEL]})
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
        LDATTACH,
        ["ip", "link", "set", "can0", "down"],
        ["ip", "link", "set", "can0", "up", *BITRATE_ARGUMENTS],
        ["ip", "link", "set", "can1", "up"],
    ]


def test_setup_can_does_not_reattach_babel(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["can0", "can1"], hardware={"can1"}, babel=True)
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    assert [call[0] for call in calls] == ["ip", "ip", "ip"]


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
    assert [call[0] for call in calls] == ["stty", "ldattach"]
