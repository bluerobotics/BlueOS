from functools import cache
from pathlib import Path

import pytest
from commonwealth.utils.general import HostOs
from flight_controller_detector.linux import navigator
from flight_controller_detector.linux.navigator import NavigatorPi4


@pytest.mark.parametrize(
    "host_os,expected_endpoints",
    [
        (HostOs.Bullseye, ["/dev/ttyS0", "/dev/ttyAMA1", "/dev/ttyAMA2", "/dev/ttyAMA3"]),
        (HostOs.Bookworm, ["/dev/ttyS0", "/dev/ttyAMA3", "/dev/ttyAMA4", "/dev/ttyAMA5"]),
        (HostOs.Trixie, ["/dev/ttyS0", "/dev/ttyAMA3", "/dev/ttyAMA4", "/dev/ttyAMA5"]),
    ],
)
def test_navigator_pi4_serials(host_os: HostOs, expected_endpoints: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(navigator, "get_host_os", lambda: host_os)
    monkeypatch.setattr(Path, "exists", lambda _: True)
    serials = NavigatorPi4.model_construct().get_serials()
    assert [serial.endpoint for serial in serials] == expected_endpoints


def test_navigator_pi4_serials_refuse_unknown_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(navigator, "get_host_os", cache(lambda: HostOs.Other))
    with pytest.raises(RuntimeError, match="Unknown release"):
        NavigatorPi4.model_construct().get_serials()


def test_navigator_pi4_serials_retry_a_host_os_that_failed_to_load(monkeypatch: pytest.MonkeyPatch) -> None:
    host_os_reads = iter([HostOs.Other, HostOs.Trixie])
    monkeypatch.setattr(navigator, "get_host_os", cache(lambda: next(host_os_reads)))
    monkeypatch.setattr(Path, "exists", lambda _self: True)

    assert NavigatorPi4.model_construct().get_serials()[1].endpoint == "/dev/ttyAMA3"
