import logging

from blueos.core import BlueOS
from features.wifi import WifiAccessPoints
from utils.retry import wait_until

SSID = "blueos-e2e"
PASSPHRASE = "blueos-e2e-pass"
logger = logging.getLogger(__name__)


def test_connect_wifi(access_points: WifiAccessPoints, blueos: BlueOS) -> None:
    with access_points.create_access_point(SSID, channel=6, passphrase=PASSPHRASE):

        def scanned() -> None:
            assert SSID in [network["ssid"] for network in blueos.wifi.scan()]

        logger.info("waiting for blueos to scan %s", SSID)
        wait_until(scanned, 60, errors=(AssertionError, RuntimeError), description=f"blueos scanning {SSID}")

        logger.info("connecting to %s", SSID)
        blueos.wifi.connect(SSID, PASSPHRASE)
        status = blueos.wifi.status()
        assert (status["ssid"], status["wpa_state"]) == (SSID, "COMPLETED"), status
        logger.info("connected to %s", SSID)
