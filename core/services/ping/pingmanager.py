import asyncio
import logging
from typing import Any, Dict, List

from serial import Serial

from ping1d_driver import Ping1DDriver
from ping360_driver import Ping360Driver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor, PingType, udp_port_is_in_use


class PingManager:
    def __init__(self) -> None:
        self.drivers: Dict[PingDeviceDescriptor, PingDriver] = {}
        self.ping1d_base_port: int = 9090
        self.ping360_base_port: int = 9092

    def stop_driver_at_port(self, port: Serial) -> None:
        """Stops the driver instance running for port "port" """
        ping_at_port = list(filter(lambda ping: ping.port == port, self.drivers.keys()))
        if ping_at_port:
            self.drivers[ping_at_port[0]].stop()
            del self.drivers[ping_at_port[0]]

    async def register_ethernet_ping360(self, ping: PingDeviceDescriptor) -> None:
        if ping not in self.drivers:
            self.drivers[ping] = Ping360Driver(ping, -1)

    async def find_next_port(self, base_port: int, direction: int) -> int:
        """
        Find the next unused udp port, starts on base_port and increments/decrements
        accordingly to direction
        """
        port = base_port
        while udp_port_is_in_use(port):
            port += direction
            await asyncio.sleep(0.1)
        return port

    async def launch_driver_instance(self, ping: PingDeviceDescriptor) -> None:
        """Launches a new driver instance for the PingDeviceDescriptor "ping"."""
        driver: PingDriver
        if ping.ping_type == PingType.PING1D:
            logging.info("Launching ping1d driver")
            port = await self.find_next_port(self.ping1d_base_port, step=-1)
            driver = Ping1DDriver(ping, port)
        elif ping.ping_type == PingType.PING360:
            logging.info("Launching ping360 driver")
            port = await self.find_next_port(self.ping360_base_port, step=+1)
            driver = Ping360Driver(ping, port)

        self.drivers[ping] = driver
        loop = asyncio.get_running_loop()
        loop.create_task(driver.start())

    def devices(self) -> List[PingDeviceDescriptor]:
        return list(self.drivers.keys())

    def update_device_settings(self, sensor_settings: Dict[str, Any]) -> None:
        found = [
            driver
            for (sensor, driver) in self.drivers.items()
            if sensor.port is not None and sensor.port.device == sensor_settings["port"]
        ]
        if not found:
            raise ValueError(f"unknown device: {sensor_settings}")
        found[0].update_settings(sensor_settings)
