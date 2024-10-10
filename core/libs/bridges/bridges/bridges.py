import logging
import shlex
import time
from enum import Enum
from shutil import which
from subprocess import PIPE, Popen

from serial.tools.list_ports_linux import SysFS

from bridges.serialhelper import Baudrate


class Status(Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    DEAD = "DEAD"


# pylint: disable=too-many-arguments
class Bridge:
    """Basic abstraction of Bridges. Used to bridge serial devices to UDP ports"""

    def __init__(
        self,
        serial_port: SysFS,
        baud: Baudrate,
        ip: str,
        udp_target_port: int,
        udp_listen_port: int,
        automatic_disconnect: bool = True,
    ) -> None:
        bridges = which("bridges")
        self.status = Status.STARTING
        automatic_disconnect_clients = "" if automatic_disconnect else "--no-udp-disconnection"
        is_server = ip == "0.0.0.0"
        port = udp_listen_port if is_server else udp_target_port
        self.output: str = ""
        command_line = f"{bridges} -u {ip}:{port} -p {serial_port.device}:{baud} {automatic_disconnect_clients}"
        if not is_server and udp_listen_port != 0:
            command_line += f" --listen-port {udp_listen_port}"

        logging.info(f"Launching bridge link with command '{command_line}'.")
        # pylint: disable=consider-using-with
        self.process = Popen(shlex.split(command_line), stdout=PIPE, stderr=PIPE)
        time.sleep(1.0)
        if self.process.poll() is not None:
            _stdout, strerr = self.process.communicate()
            error = strerr.decode("utf-8") if strerr else "Empty error"
            raise RuntimeError(f'Failed to initialize bridge, code: {self.process.returncode}, message: "{error}".')
        self.status = Status.RUNNING

    def stop(self) -> None:
        self.status = Status.STOPPING
        if not self.process:
            raise RuntimeError("Bridges process doesn't exist.")
        self.process.kill()
        time.sleep(1.0)
        if self.process.poll() is None:
            raise RuntimeError("Failed to kill bridges process.")
        self.status = Status.DEAD

    def commmunicate(self) -> tuple[bytes, bytes]:
        if not self.process:
            self.status = Status.DEAD
            raise RuntimeError("Bridges process doesn't exist.")
        output, error = self.process.communicate()
        self.output += output.decode("utf-8") + error.decode("utf-8")
        # Limit the size of self.output to 1000 characterxs
        if len(self.output) > 1000:
            self.output = self.output[-1000:]
        return output, error

    def __del__(self) -> None:
        self.stop()
