from functools import cache
from pathlib import Path

import pytest
import typedefs
from commonwealth.utils.general import HostOs
from flight_controller_detector.linux import navigator
from flight_controller_detector.linux.navigator import NavigatorPi4

BULLSEYE_ENDPOINTS = ["/dev/ttyS0", "/dev/ttyAMA1", "/dev/ttyAMA2", "/dev/ttyAMA3"]
BOOKWORM_ENDPOINTS = ["/dev/ttyS0", "/dev/ttyAMA3", "/dev/ttyAMA4", "/dev/ttyAMA5"]


class ExistingPath(type(Path())):  # type: ignore[misc]
    def exists(self, **_kwargs: object) -> bool:
        return True


@pytest.fixture(autouse=True)
def every_serial_device_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only the Serial validator in typedefs looks for the device nodes
    monkeypatch.setattr(typedefs, "Path", ExistingPath)


def endpoints() -> list[str]:
    return [serial.endpoint for serial in NavigatorPi4.model_construct().get_serials()]


@pytest.mark.parametrize(
    "host_os,expected_endpoints",
    [
        (HostOs.Bullseye, BULLSEYE_ENDPOINTS),
        (HostOs.Bookworm, BOOKWORM_ENDPOINTS),
        (HostOs.Trixie, BOOKWORM_ENDPOINTS),
        (HostOs.NixOS, BOOKWORM_ENDPOINTS),
    ],
)
def test_navigator_pi4_serials(host_os: HostOs, expected_endpoints: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(navigator, "get_host_os", lambda: host_os)
    assert endpoints() == expected_endpoints


def test_navigator_pi4_serials_default_to_bullseye_for_an_unknown_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(navigator, "get_host_os", cache(lambda: HostOs.Other))
    assert endpoints() == BULLSEYE_ENDPOINTS


def test_navigator_pi4_serials_retry_a_host_os_that_failed_to_load(monkeypatch: pytest.MonkeyPatch) -> None:
    host_os_reads = iter([HostOs.Other, HostOs.Trixie])
    monkeypatch.setattr(navigator, "get_host_os", cache(lambda: next(host_os_reads)))
    assert endpoints() == BOOKWORM_ENDPOINTS
