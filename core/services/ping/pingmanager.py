import logging
from typing import Dict, List

from serial import Serial

from ping1d_driver import Ping1DDriver
from ping360_driver import Ping360Driver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor, PingType


class PingManager:
    def __init__(self) -> None:
        self.drivers: Dict[PingDeviceDescriptor, PingDriver] = {}
        self.ping1d_current_port: int = 9090
        self.ping360_current_port: int = 9092

    def stop_driver_at_port(self, port: Serial) -> None:
        """Stops the driver instance running for port "port" """
        ping_at_port = list(filter(lambda ping: ping.port == port, self.drivers.keys()))
        if ping_at_port:
            self.drivers[ping_at_port[0]].stop()
            del self.drivers[ping_at_port[0]]

    async def launch_driver_instance(self, ping: PingDeviceDescriptor) -> None:
        """Launches a new driver instance for the PingDeviceDescriptor "ping"."""
        driver: PingDriver
        if ping.ping_type == PingType.PING1D:
            logging.info("Launching ping1d driver")
            driver = Ping1DDriver(ping, self.ping1d_current_port)
        elif ping.ping_type == PingType.PING360:
            logging.info("Launching ping360 driver")
            driver = Ping360Driver(ping, self.ping360_current_port)

        self.drivers[ping] = driver
        loop = asyncio.get_running_loop()
        loop.create_task(driver.start())

    def devices(self) -> List[PingDeviceDescriptor]:
        return list(self.drivers.keys())
