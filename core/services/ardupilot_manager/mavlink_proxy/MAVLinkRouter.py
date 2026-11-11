import asyncio
import os
import pathlib
import re
import subprocess
import tempfile
from typing import Optional

from loguru import logger

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from typedefs import TLogMode


class MAVLinkRouter(AbstractRouter):
    def __init__(self) -> None:
        super().__init__()
        self._conf_file = pathlib.Path(tempfile.gettempdir()) / f"mavlink-router-{os.getpid()}-{id(self)}.conf"

    def add_endpoint(self, endpoint: Endpoint) -> None:
        if endpoint.connection_type == EndpointType.TCPServer and any(
            existing.connection_type == EndpointType.TCPServer and existing.name != endpoint.name
            for existing in self.endpoints()
        ):
            logger.error(f"MAVLinkRouter only supports one TCP server. Skipping '{endpoint}'.")
            return
        super().add_endpoint(endpoint)

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
            if endpoint.connection_type == EndpointType.Serial:
                return f"{endpoint.place}:{endpoint.argument}"
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
        filtered_endpoints = sorted(
            Endpoint.filter_enabled(self.endpoints()),
            key=lambda endpoint: types_order[endpoint.connection_type],  # type: ignore
        )
        endpoints = " ".join([convert_endpoint(endpoint) for endpoint in filtered_endpoints])

        if master_endpoint.connection_type not in [
            EndpointType.UDPServer,
            EndpointType.Serial,
            EndpointType.TCPServer,
            EndpointType.TCPClient,
        ]:
            raise ValueError(
                f"Master endpoint of type {master_endpoint.connection_type} not supported on MavlinkRouter."
            )

        def tlog_endpoint(mode: TLogMode) -> str:
            if mode == TLogMode.disabled:
                return ""
            if mode == TLogMode.while_armed:
                # LogMode only exists in the configuration file, written by start
                return f" --telemetry-log -c {self._conf_file}"
            if mode == TLogMode.always:
                return " --telemetry-log"
            raise ValueError(f"TLog mode {mode} not supported on MavlinkRouter.")

        command = f"{self.binary()} {convert_endpoint(master_endpoint)} {endpoints} -l {self.logdir()}{tlog_endpoint(self.tlog_mode())}"
        return command

    async def start(self, master_endpoint: Endpoint) -> None:
        if self.tlog_mode() == TLogMode.while_armed:
            await asyncio.to_thread(self._conf_file.write_text, "[General]\nLogMode=while-armed\n", encoding="utf-8")
        await super().start(master_endpoint)

    async def exit(self) -> None:
        await super().exit()
        self._conf_file.unlink(missing_ok=True)

    @staticmethod
    def name() -> str:
        return "MAVLinkRouter"

    @staticmethod
    def supports_tlog() -> bool:
        return True

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
        if endpoint.connection_type not in valid_connection_types:
            raise ValueError(f"Connection_type '{endpoint.connection_type}' not supported by {MAVLinkRouter.name()}.")

    @staticmethod
    def is_ok() -> bool:
        try:
            mavlink_router = MAVLinkRouter()
            return mavlink_router.binary() is not None and mavlink_router.version() is not None
        except Exception as _:
            return False
