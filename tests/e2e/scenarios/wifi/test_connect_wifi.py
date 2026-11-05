import logging

from blueos.core import BlueOS
from features.wifi import WifiAccessPoints
from utils.retry import wait_until

SSID = "blueos-e2e"
PASSPHRASE = "blueos-e2e-pass"
logger = logging.getLogger(__name__)


def test_connect_wifi(access_points: WifiAccessPoints, blueos: BlueOS) -> None:
    access_point = access_points.create_access_point(SSID, channel=6, passphrase=PASSPHRASE)
    try:
        logger.info("waiting for blueos to scan %s", SSID)
        wait_until(lambda: next(network for network in blueos.wifi.scan() if network["ssid"] == SSID), 60)

        logger.info("connecting to %s", SSID)
        blueos.wifi.connect(SSID, PASSPHRASE)

        def connected() -> None:
            status = blueos.wifi.status()
            assert (status["ssid"], status["wpa_state"]) == (SSID, "COMPLETED"), status

        wait_until(connected, 60, interval=2, errors=(AssertionError,))
        logger.info("connected to %s", SSID)
    finally:
        access_point.remove()
        if any(network["ssid"] == SSID for network in blueos.wifi.saved()):
            blueos.wifi.remove(SSID)
