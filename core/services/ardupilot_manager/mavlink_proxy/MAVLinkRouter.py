import re
import subprocess

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from typing import Optional


class MAVLinkRouter(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()

    def _get_version(self) -> Optional[str]:
        binary = self.binary()
        assert binary is not None
        for line in subprocess.check_output([binary, "--version"]).decode("utf-8").split("\n"):
            if "version" in line:
                regex = re.search(r"version\ (?P<version>\d+)\b", line)
                if regex:
                    return regex.group("version")

        return None

    def assemble_command(self, master: Endpoint) -> str:
        # Convert endpoint format to mavlink-router format
        def convert_endpoint(endpoint: Endpoint) -> str:
            return str(endpoint)[str(endpoint).find(":") + 1 :]

        endpoints = " ".join(["--endpoint " + convert_endpoint(endpoint) for endpoint in self.endpoints()])

        if master.connType not in [
            EndpointType.UDPServer,
            EndpointType.UDPClient,
            EndpointType.Serial,
        ]:
            raise NotImplementedError

        log = f"--log {self.logdir().resolve()}"
        return f"{self.binary()} {convert_endpoint(master)} {log} {endpoints}"

    @staticmethod
    def name() -> str:
        return "MAVLinkRouter"

    @staticmethod
    def binary_name() -> str:
        return "mavlink-routerd"

    @staticmethod
    def _validate_endpoint(endpoint: Endpoint) -> bool:
        return endpoint.connType in [
            EndpointType.UDPServer,
            EndpointType.UDPClient,
            EndpointType.Serial,
        ]

    @staticmethod
    def is_ok() -> bool:
        try:
            mavlink_router = MAVLinkRouter()
            return mavlink_router.binary() is not None and mavlink_router.version() is not None
        except Exception as _:
            return False
