import subprocess
from typing import Any, List

import pytest
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from typedefs import Platform

BITRATE_ARGUMENTS = ["type", "can", "bitrate", "1000000", "restart-ms", "100", "loopback", "off"]


def make_board() -> LinuxFlightController:
    return LinuxFlightController(name="Test", platform=Platform.Navigator)


def fake_sysfs(monkeypatch: pytest.MonkeyPatch, interfaces: List[str]) -> None:
    monkeypatch.setattr(LinuxFlightController, "can_interfaces", lambda _self: sorted(interfaces))


def record_ip_calls(monkeypatch: pytest.MonkeyPatch, fail: bool = False) -> List[List[str]]:
    calls: List[List[str]] = []

    def fake_run(arguments: List[str], **_kwargs: Any) -> "subprocess.CompletedProcess[str]":
        calls.append(arguments)
        if fail:
            raise subprocess.CalledProcessError(1, arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_setup_can_skips_missing_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=[])
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    assert not calls


def test_setup_can_configures_every_hardware_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["can0", "can1"])
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    # A stale loopback mode has to be cleared, and a real controller has to recover from bus-off on its own.
    assert calls == [
        ["ip", "link", "set", "can0", "down"],
        ["ip", "link", "set", "can0", "up", *BITRATE_ARGUMENTS],
        ["ip", "link", "set", "can1", "down"],
        ["ip", "link", "set", "can1", "up", *BITRATE_ARGUMENTS],
    ]


def test_setup_can_failure_does_not_block_autopilot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sysfs(monkeypatch, interfaces=["can0"])
    record_ip_calls(monkeypatch, fail=True)

    make_board().setup_can()


def test_setup_can_unreadable_sysfs_does_not_block_autopilot(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(_self: LinuxFlightController) -> List[str]:
        raise PermissionError("/sys/class/net")

    monkeypatch.setattr(LinuxFlightController, "can_interfaces", unreadable)
    calls = record_ip_calls(monkeypatch)

    make_board().setup_can()

    assert not calls
