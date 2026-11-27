from typing import Any

from blueos.core import BlueOS
from features.network import Router
from utils.retry import wait_until


def test_blueos_counts_eth0_unplugged_and_plugged_back(router: Router, blueos: BlueOS) -> None:
    def eth0() -> dict[str, Any]:
        info: dict[str, Any] = blueos.cable_guy.ethernet("eth0")["info"]
        return info

    def connected(expected: bool) -> None:
        info = eth0()
        assert info["connected"] == expected, info

    disconnections = eth0()["number_of_disconnections"]
    with router.without_vehicle_cable():
        wait_until(lambda: connected(False), 60, errors=(AssertionError,), description="BlueOS seeing eth0 unplugged")
    wait_until(lambda: connected(True), 60, errors=(AssertionError,), description="BlueOS seeing eth0 plugged")
    info = eth0()
    assert info["number_of_disconnections"] > disconnections, info
