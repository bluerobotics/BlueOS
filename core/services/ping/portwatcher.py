import asyncio
import logging
from typing import Callable, Dict, Optional, Set
from warnings import warn

import serial.tools.list_ports
from serial.tools.list_ports_linux import SysFS

from pingutils import PingDeviceDescriptor

MAX_ATTEMPTS = 10


class PortWatcher:
    """Watches the Serial ports on the system, calls set_prober when a port is found,
    port_post_callback when a port is no longe present"""

    def __init__(self, probe_callback: Callable[[SysFS], Optional[PingDeviceDescriptor]]) -> None:
        logging.info("PortWatcher Started")
        self.known_ports: Set[str] = set()
        self.probe_callback: Callable[[SysFS], Optional[PingDeviceDescriptor]] = probe_callback
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

    def probe_port(self, port: SysFS) -> None:
        """Attempts to probe port "port" for up to MAX_ATTEMPTS times"""
        logging.info(f"Probing port: {port.hwid}")
        if port in self.known_ports:
            warn(f"Developer error: Port is already known, but being probed again: {port}")
            return
        attempts = self.probe_attempts_counter.get(port, 0)
        good_port = self.probe_callback(port)
        if good_port:
            self.known_ports.add(port)
        attempts += 1
        self.probe_attempts_counter[port] = attempts
        if attempts == MAX_ATTEMPTS:
            logging.info(f"Max number of probing attempts reached for {port}. Giving up.")

    async def start_watching(self) -> None:
        """Start watching for plugged/unplugged serial devices in the system"""
        # TODO: try https://pypi.org/project/inotify/
        while True:
            ports = serial.tools.list_ports.comports()
            logging.debug(f"Currently detected ports: {ports}")
            found_ports = set()
            for port in ports:
                if self.port_should_be_probed(port):
                    self.probe_port(port)
                found_ports.add(port)

            missing = self.known_ports - found_ports
            for port in missing:
                logging.info(f"Port lost: {port.hwid}")
                self.known_ports.remove(port)
                if self.port_lost_callback is not None:
                    self.port_lost_callback(port)

            await asyncio.sleep(1)
