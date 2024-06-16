import asyncio
from typing import Any, Callable, Coroutine, Dict, Optional, Set
from warnings import warn

import serial.tools.list_ports
from loguru import logger
from serial.tools.list_ports_linux import SysFS

from ping360_ethernet_prober import find_ping360_ethernet
from pingutils import PingDeviceDescriptor

MAX_ATTEMPTS = 3


class PortWatcher:
    """Watches the Serial ports on the system.
    Calls set_prober when a port is found, and port_post_callback when a port is no longer present."""

    def __init__(
        self,
        probe_callback: Callable[[Any], Coroutine[Any, SysFS, Optional[PingDeviceDescriptor]]],
        found_callback: Callable[[Any], Coroutine[Any, SysFS, Optional[PingDeviceDescriptor]]],
    ) -> None:
        logger.info("PortWatcher Started")
        self.known_ports: Set[str] = set()
        self.known_ips: Set[str] = set()

        self.probe_callback: Callable[[Any], Coroutine[Any, SysFS, Optional[PingDeviceDescriptor]]] = probe_callback
        self.ethernet_ping_found_callback: Callable[
            [Any], Coroutine[Any, SysFS, Optional[PingDeviceDescriptor]]
        ] = found_callback
        self.port_lost_callback: Optional[Callable[[SysFS], None]] = None
        self.probe_attempts_counter: Dict[SysFS, int] = {}

    def set_port_post_callback(self, callback: Callable[[SysFS], None]) -> None:
        self.port_lost_callback = callback

    def port_should_be_probed(self, port: SysFS) -> bool:
        """A port should be probed if there hasn't been MAX_ATTEMPTS to probe it yet
        and it is caught by our filters
        """
        if port in self.known_ports:
            return False
        if self.probe_attempts_counter.get(port, 0) >= MAX_ATTEMPTS:
            return False
        return True

    async def probe_port(self, port: SysFS) -> None:
        """Attempts to probe "port" for up to MAX_ATTEMPTS times."""
        logger.info(f"Probing port: {port.hwid}")
        if port in self.known_ports:
            warn(f"Developer error: Port is already known, but being probed again: {port}")
            return
        attempts = self.probe_attempts_counter.get(port, 0)
        good_port = await self.probe_callback(port)
        if good_port:
            self.known_ports.add(port)
        attempts += 1
        self.probe_attempts_counter[port] = attempts
        if attempts == MAX_ATTEMPTS:
            logger.info(f"Max number of probing attempts reached for {port}. Giving up.")

    async def add_ping360(self) -> None:
        devices_list = await find_ping360_ethernet()
        # find_ping360_ethernet sets the discovery info, but cast it so mypy doesn't complain
        ip_devices = {str(device.ethernet_discovery_info): device for device in devices_list}
        ips = set(ip_devices)
        lost_ips = self.known_ips - ips
        new_ips = ips - self.known_ips
        for ip in lost_ips:
            if self.port_lost_callback is not None:
                self.port_lost_callback(ip)
            self.known_ips.remove(ip)
        for ip in new_ips:
            self.known_ips.add(ip)
            await self.ethernet_ping_found_callback(ip_devices[ip])

    async def start_watching(self) -> None:
        """Start watching for plugged/unplugged serial devices in the system."""
        # TODO: try https://pypi.org/project/inotify/
        while True:
            ports = serial.tools.list_ports.comports()
            ports_description = [f"{port.subsystem}:{port.name}" for port in ports]
            logger.debug(f"Currently detected ports: {ports_description}")
            found_ports = set()
            for port in ports:
                if self.port_should_be_probed(port):
                    await self.probe_port(port)
                found_ports.add(port)

            missing = self.known_ports - found_ports
            for port in missing:
                logger.info(f"Port lost: {port.hwid}")
                self.known_ports.remove(port)
                if self.port_lost_callback is not None:
                    self.port_lost_callback(port)
            await self.add_ping360()
            await asyncio.sleep(1)
