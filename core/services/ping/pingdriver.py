import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bridges.bridges import Bridge
from bridges.serialhelper import Baudrate, set_low_latency
from brping import PingDevice
from brping.definitions import COMMON_DEVICE_INFORMATION
from loguru import logger
from ping_exceptions import InvalidDeviceDescriptor, NoUDPPortAssignedToPingDriver
from pingutils import PingDeviceDescriptor
from serial.tools.list_ports_linux import SysFS
from typedefs import DriverStatus


@dataclass
class BridgeConfig:
    serial_port: SysFS
    baud: Baudrate
    udp_port: int


class PingDriver:
    def __init__(self, ping: PingDeviceDescriptor, port: Optional[int]) -> None:
        self.ping = ping
        self.port = port
        self.bridge: Optional[Bridge] = None
        self.bridge_config: Optional[BridgeConfig] = None
        self.ping.driver = self
        self.driver_status = DriverStatus(udp_port=port, mavlink_driver_enabled=False)

    @staticmethod
    def detect_highest_baud(port: SysFS) -> Baudrate:
        """Tries to communicate in increasingly high baudrates up to 4M
        returns the highest one with at least 90% success rate.
        """
        failure_threshold = 0.1  # allow up to 10% failure rate
        attempts = 10  # try up to 10 times per baudrate
        max_failures = attempts * failure_threshold
        last_valid_baud: Optional[Baudrate] = None

        for baud in Baudrate:
            # Ping1D hangs with a baudrate bigger than 3M, going to ignore it for now
            if baud > 3000000:
                continue
            logger.debug(f"Trying baud {baud}...")
            failures = 0
            ping = PingDevice()
            ping.connect_serial(port.device, baud)
            for _ in range(attempts):
                device_info = None
                try:
                    device_info = ping.request(COMMON_DEVICE_INFORMATION, timeout=0.1)
                except Exception as e:
                    logger.warning(f"Failed to request device information during baudrate detection: {e}")
                if device_info is None:
                    failures += 1
                    if failures > max_failures:
                        break  # there's no pointing in testing again if we already failed.
            if failures <= max_failures:
                last_valid_baud = baud
            logger.debug(f"Baudrate {baud} is {'valid' if baud==last_valid_baud else 'invalid'}")
        if last_valid_baud is None:
            raise RuntimeError("No valid baudrate detected")
        logger.info(f"Highest baudrate detected: {last_valid_baud}")
        return last_valid_baud

    @staticmethod
    def open_bridge(config: BridgeConfig) -> Bridge:
        PingDevice().connect_serial(config.serial_port.device, config.baud)
        set_low_latency(config.serial_port)
        return Bridge(config.serial_port, config.baud, "0.0.0.0", 0, config.udp_port, automatic_disconnect=False)

    async def start(self) -> None:
        """Starts the driver"""
        if self.ping.port is None:
            raise InvalidDeviceDescriptor("PingDeviceDescriptor has no usable port.")

        if self.port is None:
            raise NoUDPPortAssignedToPingDriver("PingDriver attempted to stash with no UDP port.")

        serial_port = self.ping.port
        udp_port = self.port
        baud = await asyncio.to_thread(self.detect_highest_baud, serial_port)
        self.bridge_config = BridgeConfig(serial_port, baud, udp_port)
        self.bridge = await asyncio.to_thread(self.open_bridge, self.bridge_config)

    def stop(self) -> None:
        """Stops the driver"""
        logger.info(f"Forcing Ping1d at port {self.port} to stop.")
        self.ping.driver = None
        if self.bridge:
            self.bridge.stop()

    def update_settings(self, sensor_settings: Dict[str, Any]) -> None:
        if "mavlink_driver" in sensor_settings:
            self.set_mavlink_driver_running(sensor_settings["mavlink_driver"])

    def set_mavlink_driver_running(self, should_run: bool) -> None:
        pass

    def __del__(self) -> None:
        self.stop()
