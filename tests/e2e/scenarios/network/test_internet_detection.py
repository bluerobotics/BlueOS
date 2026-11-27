from blueos.core import BlueOS
from features.network import Router
from utils.retry import wait_until


def test_blueos_detects_losing_and_regaining_internet(router: Router, blueos: BlueOS) -> None:
    def online(expected: bool) -> None:
        sites = blueos.helper.internet_access()
        assert any(site["online"] for site in sites.values()) == expected, sites

    with router.without_internet():
        wait_until(lambda: online(False), 120, errors=(AssertionError,), description="BlueOS seeing it is offline")
    wait_until(lambda: online(True), 120, errors=(AssertionError,), description="BlueOS seeing it is online")
