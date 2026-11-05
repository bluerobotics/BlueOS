import logging

from blueos.core import BlueOS
from features.wifi import WifiScanner
from utils.retry import wait_until

logger = logging.getLogger(__name__)


def test_hotspot(blueos: BlueOS, scanner: WifiScanner) -> None:
    ssid = blueos.wifi.hotspot_credentials()["ssid"]

    logger.info("enabling hotspot %s", ssid)
    assert blueos.wifi.enable_hotspot()
    assert blueos.wifi.hotspot_enabled()

    def visible() -> None:
        assert ssid in scanner.scan()

    wait_until(visible, 60, errors=(AssertionError,))
    logger.info("hotspot %s seen by an outside client", ssid)
