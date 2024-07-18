import re
import subprocess
from typing import Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint
from typedefs import EndpointType


class MAVP2P(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()

    def _get_version(self) -> Optional[str]:
        binary = self.binary()
        assert binary is not None
        for line in subprocess.check_output([binary, "--version"]).decode("utf-8").split("\n"):
            regex = re.search(r"v(?P<version>\S+)\b", line)
            if regex:
                return regex.group("version")

        return None

    def assemble_command(self, master_endpoint: Endpoint) -> str:
        # Convert endpoint format to mavlink-router format
        def convert_endpoint(endpoint: Endpoint) -> str:
            if endpoint.connection_type == EndpointType.Serial:
                return f"serial:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.TCPServer:
                return f"tcps:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.TCPClient:
                return f"tcpc:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPServer:
                return f"udps:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPClient:
                return f"udpc:{endpoint.place}:{endpoint.argument}"
            raise ValueError(f"Endpoint of type {endpoint.connection_type} not supported on MAVP2P.")

        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in [master_endpoint, *self.endpoints()]])

        return f"{self.binary()} {endpoints} --streamreq-disable"

    @staticmethod
    def name() -> str:
        return "MAVP2P"

    @staticmethod
    def binary_name() -> str:
        return "mavp2p"

    @staticmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        valid_connection_types = [
            EndpointType.UDPClient,
            EndpointType.UDPServer,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
            EndpointType.Serial,
        ]
        if endpoint.connection_type not in valid_connection_types:
            raise ValueError(f"Connection_type '{endpoint.connection_type}' not supported by {MAVP2P.name()}.")

    @staticmethod
    def is_ok() -> bool:
        try:
            router = MAVP2P()
            return router.binary() is not None and router.version() is not None
        except Exception as _:
            return False
