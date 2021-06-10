import logging
from typing import Optional

from brping import PingDevice
from brping.definitions import COMMON_DEVICE_INFORMATION

from bridges import Bridges
from pingutils import PingDeviceDescriptor
from serialhelper import Baudrates, set_low_latency


class PingDriver:
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        self.ping = ping
        self.port = port
        self.bridge: Optional[Bridges] = None

    def detect_highest_baud(self) -> Baudrates:
        """Tries to communicate in increasingly high baudrates up to 4M
        returns the highest one with at least 90% success rate.
        """
        failure_threshold = 0.1  # allow up to 10% failure rate
        attempts = 10  # try up to 10 times per baudrate
        max_failures = attempts * failure_threshold

        last_valid_baud = Baudrates.b115200
        for baud in Baudrates:
            logging.debug(f"Trying baud {baud}...")
            failures = 0
            ping = PingDevice()
            ping.connect_serial(self.ping.port.device, baud)
            for _ in range(attempts):
                device_info = ping.request(COMMON_DEVICE_INFORMATION, timeout=0.1)
                if device_info is None:
                    failures += 1
                    if failures > max_failures:
                        break  # there's no pointing in testing again if we already failed.
            if failures <= max_failures:
                last_valid_baud = baud
            logging.debug(f"Baudrate {baud} is {'valid' if baud==last_valid_baud else 'invalid'}")
        logging.info(f"Highest baudrate detected: {last_valid_baud}")
        return last_valid_baud

    def start(self) -> None:
        """Starts the driver"""
        baud = self.detect_highest_baud()
        # Do a ping connection to set the baudrate
        PingDevice().connect_serial(self.ping.port.device, baud)
        set_low_latency(self.ping.port)
        self.bridge = Bridges(self.ping.port, baud, "0.0.0.0", self.port)

    def stop(self) -> None:
        """Stops the driver"""
        logging.info(f"Forcing Ping1d at port {self.port} to stop.")

    def __del__(self) -> None:
        self.stop()
