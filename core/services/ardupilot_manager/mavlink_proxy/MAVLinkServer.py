import re
import subprocess
from typing import Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType


class MAVLinkServer(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()

    def _get_version(self) -> Optional[str]:
        binary = self.binary()
        assert binary is not None
        for line in subprocess.check_output([binary, "--version"]).decode("utf-8").split("\n"):
            regex = re.search(r"mavlink-server (?P<version>\S+)\b", line)
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
            raise ValueError(f"Endpoint of type {endpoint.connection_type} not supported on MAVLink-Server.")

        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in [master_endpoint, *self.endpoints()]])

        return f"{self.binary()} {endpoints}"

    @staticmethod
    def name() -> str:
        return "MAVLink-Server"

    @staticmethod
    def binary_name() -> str:
        return "mavlink-server"

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
            raise ValueError(f"Connection_type '{endpoint.connection_type}' not supported by {MAVLinkServer.name()}.")

    @staticmethod
    def is_ok() -> bool:
        try:
            router = MAVLinkServer()
            return router.binary() is not None and router.version() is not None
        except Exception as _:
            return False
