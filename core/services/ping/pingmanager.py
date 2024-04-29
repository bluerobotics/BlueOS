import asyncio
from typing import Any, Dict, List, Set

from loguru import logger
from serial.tools.list_ports_linux import SysFS

from ping1d_driver import Ping1DDriver
from ping360_driver import Ping360Driver
from ping360_ethernet_driver import Ping360EthernetDriver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor, PingType, udp_port_is_in_use


class PingManager:
    def __init__(self) -> None:
        self.drivers: Dict[PingDeviceDescriptor, PingDriver] = {}
        self.connecting_ports: Set[int] = set()
        self.ping1d_base_port: int = 9090
        self.ping360_base_port: int = 9092

    def stop_driver_at_port(self, port: SysFS | str) -> None:
        """Stops the driver instance running for port "port" """
        ping_at_port = [ping for ping in self.drivers if port in [ping.port, ping.ethernet_discovery_info]]
        if ping_at_port:
            self.drivers[ping_at_port[0]].stop()
            del self.drivers[ping_at_port[0]]

    async def register_ethernet_ping360(self, ping: PingDeviceDescriptor) -> None:
        if ping not in self.drivers:
            self.drivers[ping] = Ping360EthernetDriver(ping)

    async def find_next_port(self, base_port: int, step: int) -> int:
        """
        Finds the next unused UDP port.
        Starts at 'base_port' and increments/decrements by 'step'.
        """
        port = base_port
        # Order set to minimise chance of a race condition
        while udp_port_is_in_use(port) or (port in self.connecting_ports):
            port += step
            await asyncio.sleep(0.1)
        return port

    async def launch_driver_instance(self, ping: PingDeviceDescriptor) -> None:
        """Launches a new driver instance for the PingDeviceDescriptor "ping"."""
        driver: PingDriver
        if ping.ping_type == PingType.PING1D:
            logger.info("Launching ping1d driver")
            port = await self.find_next_port(self.ping1d_base_port, step=-1)
            self.connecting_ports.add(port)  # Claim now, to prevent race
            driver = Ping1DDriver(ping, port)
        elif ping.ping_type == PingType.PING360:
            logger.info("Launching ping360 driver")
            port = await self.find_next_port(self.ping360_base_port, step=+1)
            self.connecting_ports.add(port)  # Claim now, to prevent race
            driver = Ping360Driver(ping, port)

        self.drivers[ping] = driver
        loop = asyncio.get_running_loop()
        loop.create_task(driver.start())

    def devices(self) -> List[PingDeviceDescriptor]:
        return list(self.drivers)

    def update_device_settings(self, sensor_settings: Dict[str, Any]) -> None:
        found = [
            driver
            for (sensor, driver) in self.drivers.items()
            if sensor.port is not None and sensor.port.device == sensor_settings["port"]
        ]
        if not found:
            raise ValueError(f"unknown device: {sensor_settings}")
        found[0].update_settings(sensor_settings)
