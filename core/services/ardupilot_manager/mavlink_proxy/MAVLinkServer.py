import os
import re
import subprocess
from typing import Optional

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType


class MAVLinkServer(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()
        self.log_path: Optional[str] = None
        self.mavlink_system_id: Optional[int] = None
        self.mavlink_component_id: Optional[int] = None

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
            endpoint_str = None

            if endpoint.connection_type == EndpointType.Serial:
                endpoint_str = f"serial:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.TCPServer:
                endpoint_str = f"tcps:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.TCPClient:
                endpoint_str = f"tcpc:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPServer:
                endpoint_str = f"udps:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.UDPClient:
                endpoint_str = f"udpc:{endpoint.place}:{endpoint.argument}"
            if endpoint.connection_type == EndpointType.Zenoh:
                endpoint_str = f"zenoh:{endpoint.place}:{endpoint.argument}"

            if endpoint_str is None:
                raise ValueError(f"Endpoint of type {endpoint.connection_type} not supported on MAVLink-Server.")
            return endpoint_str

        filtered_endpoints = Endpoint.filter_enabled(self.endpoints())
        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in [master_endpoint, *filtered_endpoints]])

        if not self.log_path:
            self.log_path = "/var/logs/blueos/services/mavlink-server/"
        if not self.mavlink_system_id:
            self.mavlink_system_id = int(os.environ.get("MAV_SYSTEM_ID", 1))
        if not self.mavlink_component_id:
            self.mavlink_component_id = int(os.environ.get("MAV_COMPONENT_ID_ONBOARD_COMPUTER", 191))

        return f"{self.binary()} {endpoints} --mavlink-system-id={self.mavlink_system_id} --mavlink-component-id={self.mavlink_component_id} --log-path={self.log_path}"

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
            EndpointType.Zenoh,
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
