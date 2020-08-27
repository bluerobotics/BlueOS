import pathlib
import re
import shlex
import subprocess
import tempfile

from lib.AbstractRouter import AbstractRouter
from lib.Endpoint import Endpoint, EndpointType
from typing import List, Optional


class MAVProxy(AbstractRouter):
    def __init__(self):
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
        endpoints = " ".join(["--out=" + endpoint.__str__() for endpoint in self.endpoints()])

        master_string = str(master)
        if master.connType == EndpointType.Serial:
            master_args = str(master).split(":")
            if len(master_args) == 2:
                master_string = f"{master_args[1]}"
            else:
                master_string = f"{master_args[1]} --baudrate={master_args[2]}"

        log = f"--state-basedir={self.logdir().resolve()}"
        return f"{self.binary()} --master={master_string} {endpoints} {log} --non-interactive"

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
