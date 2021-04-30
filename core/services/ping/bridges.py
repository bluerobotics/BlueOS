import logging
import shlex
from shutil import which
from subprocess import Popen

from serial.tools.list_ports_linux import SysFS

from serialhelper import Baudrates


class Bridges:
    """Basic abstraction of Bridges. Used to bridge serial devices to UDP ports"""

    def __init__(self, serial_port: SysFS, baud: Baudrates, ip: str, udp_port: int) -> None:
        bridges = which("bridges")
        command_line = f"{bridges} -u {ip}:{udp_port} -p {serial_port.device}:{baud}"
        logging.info(f"Launching {command_line}")
        # pylint: disable=consider-using-with
        self.process = Popen(shlex.split(command_line))

    def stop(self) -> None:
        if self.process:
            self.process.kill()

    def __del__(self) -> None:
        self.stop()
