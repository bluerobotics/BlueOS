import re
import subprocess
from typing import Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint
from typedefs import EndpointType


class MAVLinkRouter(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()

    def _get_version(self) -> Optional[str]:
        binary = self.binary()
        assert binary is not None
        for line in subprocess.check_output([binary, "--version"]).decode("utf-8").split("\n"):
            if "version" in line:
                regex = re.search(r"version\ (?P<version>\S+)\b", line)
                if regex:
                    return regex.group("version")

        return None

    def assemble_command(self, master_endpoint: Endpoint) -> str:
        # Convert endpoint format to mavlink-router format
        def convert_endpoint(endpoint: Endpoint) -> str:
            # TCP uses a special argument and only works with localhost
            if endpoint.connection_type == EndpointType.TCPServer:
                return f"--tcp-port {endpoint.argument}"
            if endpoint.connection_type == EndpointType.TCPClient:
                return f"--tcp-endpoint {endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPServer:
                return f"{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPClient:
                return f"--endpoint {endpoint.place}:{endpoint.argument}"
            raise ValueError(f"Endpoint of type {endpoint.connection_type} not supported on MavlinkRouter.")

        # Since MAVLinkRouter does not have an argument specifier for UDP Server connections
        # (e.g. "--endpoint" for UDP Clients), we rely on the UDP Server endpoints being
        # on the beginning of the endpoints list, and so as the first endpoints on the
        # process call, for them to work
        types_order = {
            EndpointType.UDPServer: 0,
            EndpointType.UDPClient: 1,
            EndpointType.TCPServer: 2,
            EndpointType.TCPClient: 3,
        }
        sorted_endpoints = sorted(
            self.endpoints(), key=lambda endpoint: types_order[endpoint.connection_type]  # type: ignore
        )
        filtered_endpoints = Endpoint.filter_enabled(sorted_endpoints)
        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in filtered_endpoints])

        if master_endpoint.connection_type not in [
            EndpointType.UDPServer,
            EndpointType.Serial,
            EndpointType.TCPServer,
        ]:
            raise ValueError(
                f"Master endpoint of type {master_endpoint.connection_type} not supported on MavlinkRouter."
            )

        if master_endpoint.connection_type == EndpointType.TCPServer:
            # The "--tcp-port 0" argument is used to prevent the router from binding TCP port 5760
            return f"{self.binary()} \
                --tcp-endpoint {master_endpoint.place}:{master_endpoint.argument} --tcp-port 0 {endpoints}"

        return f"{self.binary()} {master_endpoint.place}:{master_endpoint.argument} --tcp-port 0 {endpoints}"

    @staticmethod
    def name() -> str:
        return "MAVLinkRouter"

    @staticmethod
    def binary_name() -> str:
        return "mavlink-routerd"

    @staticmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        valid_connection_types = [
            EndpointType.UDPClient,
            EndpointType.UDPServer,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
        ]
        if not endpoint.connection_type in valid_connection_types:
            raise ValueError(f"Connection_type '{endpoint.connection_type}' not supported by {MAVLinkRouter.name()}.")

    @staticmethod
    def is_ok() -> bool:
        try:
            mavlink_router = MAVLinkRouter()
            return mavlink_router.binary() is not None and mavlink_router.version() is not None
        except Exception as _:
            return False
