import logging
from typing import Any, Optional

from bridges.bridges import Bridge
from bridges.serialhelper import Baudrate, set_low_latency
from brping import PingDevice
from brping.definitions import COMMON_DEVICE_INFORMATION

from pingutils import PingDeviceDescriptor




class PingDriver:
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        self.ping = ping
        self.port = port
        self.bridge: Optional[Bridge] = None
        self.driver_status: Dict[str,int|float|str|bool] = {"udp_port": port}
        self.ping.driver = self

    def detect_highest_baud(self) -> Baudrate:
        """Tries to communicate in increasingly high baudrates up to 4M
        returns the highest one with at least 90% success rate.
        """
        failure_threshold = 0.1  # allow up to 10% failure rate
        attempts = 10  # try up to 10 times per baudrate
        max_failures = attempts * failure_threshold

        last_valid_baud = Baudrate.b115200
        for baud in Baudrate:
            # Ping1D hangs with a baudrate bigger than 3M, going to ignore it for now
            if baud > 3000000:
                continue
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

    async def start(self) -> None:
        """Starts the driver"""
        baud = self.detect_highest_baud()
        # Do a ping connection to set the baudrate
        PingDevice().connect_serial(self.ping.port.device, baud)
        set_low_latency(self.ping.port)
        self.bridge = Bridge(self.ping.port, baud, "0.0.0.0", self.port, automatic_disconnect=False)

    def stop(self) -> None:
        """Stops the driver"""
        logging.info(f"Forcing Ping1d at port {self.port} to stop.")
        self.ping.driver = None
        if self.bridge:
            self.bridge.stop()

    def update_settings(self, sensor_settings: dict[str, Any]):
        if "mavlink_driver" in sensor_settings:
            self.set_mavlink_driver_running(sensor_settings["mavlink_driver"])

    def set_mavlink_driver_running(self, should_run: bool):
        pass

    def __del__(self) -> None:
        self.stop()
