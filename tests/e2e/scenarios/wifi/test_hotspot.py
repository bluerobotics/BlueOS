import logging

from blueos.core import BlueOS
from features.wifi import WifiScanner
from utils.retry import wait_until

logger = logging.getLogger(__name__)
WATCHDOG_INTERVAL = 30


def test_hotspot(blueos: BlueOS, scanner: WifiScanner) -> None:
    ssid = blueos.wifi.hotspot_credentials()["ssid"]

    def enabled() -> None:
        assert blueos.wifi.hotspot_enabled()

    wait_until(enabled, 2 * WATCHDOG_INTERVAL, interval=5, errors=(AssertionError,))
    logger.info("blueos reports hotspot %s enabled", ssid)

    def visible() -> None:
        assert ssid in scanner.scan()

    wait_until(visible, 60, errors=(AssertionError,))
    logger.info("hotspot %s seen by an outside client", ssid)
