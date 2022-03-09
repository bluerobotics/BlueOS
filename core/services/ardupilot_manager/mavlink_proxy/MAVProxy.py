import re
import subprocess
from typing import Callable, Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint
from typedefs import EndpointType


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

    def assemble_command(self, master_endpoint: Endpoint) -> str:
        serial_endpoint_as_input: Callable[[Endpoint], str] = lambda endpoint: f"{endpoint.place},{endpoint.argument}"

        # Convert endpoint format to mavproxy format
        def convert_endpoint(endpoint: Endpoint) -> str:
            if endpoint.connection_type != EndpointType.Serial:
                return f"--out={str(endpoint)}"
            return f"--out={serial_endpoint_as_input(endpoint)}"

        filtered_endpoints = Endpoint.filter_enabled(self.endpoints())
        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in filtered_endpoints])

        master_string = str(master_endpoint)
        if master_endpoint.connection_type == EndpointType.Serial:
            if not master_endpoint.argument:
                master_string = f"{master_endpoint.place}"
            else:
                master_string = f"{serial_endpoint_as_input(master_endpoint)}"
        if master_endpoint.connection_type == EndpointType.TCPServer:
            master_string = f"tcp:{master_endpoint.place}:{master_endpoint.argument}"

        log = f"--state-basedir={self.logdir().resolve()}"
        return f"{self.binary()} --master={master_string} {endpoints} {log} --non-interactive"

    @staticmethod
    def name() -> str:
        return "MAVProxy"

    @staticmethod
    def binary_name() -> str:
        return "mavproxy.py"

    @staticmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        valid_connection_types = [
            EndpointType.Serial,
            EndpointType.UDPServer,
            EndpointType.UDPClient,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
        ]
        if not endpoint.connection_type in valid_connection_types:
            raise ValueError(f"Connection_type '{endpoint.connection_type}' not supported by router {MAVProxy.name()}.")

    @staticmethod
    def is_ok() -> bool:
        try:
            mavproxy = MAVProxy()
            return mavproxy.binary() is not None and mavproxy.version() is not None
        except Exception as _:
            return False
