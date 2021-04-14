import re
import subprocess
from typing import Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType


class MAVProxy(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()

    def _get_version(self) -> Optional[str]:
        binary = self.binary()
        assert binary is not None
        for line in subprocess.check_output([binary, "--version"]).decode("utf-8").split("\n"):
            if "Version" in line:
                regex = re.search(r"(?P<version>\d+.\d+.\d+)", line)
                if regex:
                    return regex.group("version")
        return None

    def assemble_command(self, master: Endpoint) -> str:
        endpoints_string = ""
        for endpoint in self.endpoints():
            if endpoint.connection_type != EndpointType.Serial:
                endpoints_string += f" --out={str(endpoint)}"
            else:
                endpoints_string += f" --out={endpoint.place},{endpoint.argument}"

        master_string = str(master)
        if master.connection_type == EndpointType.Serial:
            if not master.argument:
                master_string = f"{master.place}"
            else:
                master_string = f"{master.place},{master.argument}"

        log = f"--state-basedir={self.logdir().resolve()}"
        return f"{self.binary()} --master={master_string} {endpoints_string} {log} --non-interactive"

    @staticmethod
    def name() -> str:
        return "MAVProxy"

    @staticmethod
    def binary_name() -> str:
        return "mavproxy.py"

    @staticmethod
    def _validate_endpoint(endpoint: Endpoint) -> bool:
        return True

    @staticmethod
    def is_ok() -> bool:
        try:
            mavproxy = MAVProxy()
            return mavproxy.binary() is not None and mavproxy.version() is not None
        except Exception as _:
            return False
