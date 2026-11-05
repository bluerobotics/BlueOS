from collections.abc import Iterator

import pytest
from blueos.core import BlueOS
from features.wifi import WifiAccessPoints, WifiScanner
from targets.target import Target


@pytest.fixture(autouse=True)
def forget_networks_saved_by_test(blueos: BlueOS) -> Iterator[None]:
    blueos.wifi.wait_ready()
    saved = {network["ssid"] for network in blueos.wifi.saved()}
    yield
    for network in blueos.wifi.saved():
        if network["ssid"] not in saved:
            blueos.wifi.remove(network["ssid"])


@pytest.fixture
def access_points(target: Target) -> WifiAccessPoints:
    return target.feature(WifiAccessPoints)


@pytest.fixture
def scanner(target: Target) -> WifiScanner:
    return target.feature(WifiScanner)
