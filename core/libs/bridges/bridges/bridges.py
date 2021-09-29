import logging
import shlex
import time
from shutil import which
from subprocess import PIPE, Popen

from serial.tools.list_ports_linux import SysFS

from bridges.serialhelper import Baudrate


class Bridge:
    """Basic abstraction of Bridges. Used to bridge serial devices to UDP ports"""

    def __init__(self, serial_port: SysFS, baud: Baudrate, ip: str, udp_port: int) -> None:
        bridges = which("bridges")
        command_line = f"{bridges} -u {ip}:{udp_port} -p {serial_port.device}:{baud}"
        logging.info(f"Launching bridge link with command '{command_line}'.")
        # pylint: disable=consider-using-with
        self.process = Popen(shlex.split(command_line), stdout=PIPE, stderr=PIPE)
        time.sleep(1.0)
        if self.process.poll() is not None:
            error = self.process.communicate()[1]
            raise RuntimeError(f"Failed to initialize bridge: {self.process.returncode} - {error.decode('utf-8')}.")

    def stop(self) -> None:
        if not self.process:
            raise RuntimeError("Bridges process doesn't exist.")
        self.process.kill()
        time.sleep(1.0)
        if self.process.poll() is None:
            raise RuntimeError("Failed to kill bridges process.")

    def __del__(self) -> None:
        self.stop()
