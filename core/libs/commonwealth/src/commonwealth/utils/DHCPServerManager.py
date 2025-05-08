import asyncio
import pathlib
import shutil
import subprocess
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Any, List, Optional, Tuple

import psutil
from loguru import logger

from commonwealth.utils.DHCPDiscovery import discover_dhcp_servers


# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes
class Dnsmasq:
    def __init__(
        self,
        interface: str,
        ipv4_gateway: IPv4Address,
        subnet_mask: Optional[IPv4Address] = None,
        lease_range: Tuple[int, int] = (101, 200),
        lease_time: str = "24h",
        backup: bool = False,
    ) -> None:
        self._subprocess: Optional[Any] = None

        if interface not in psutil.net_if_stats():
            raise ValueError(f"Interface '{interface}' not found. Available interfaces are {psutil.net_if_stats()}.")
        self._interface = interface
        self._is_backup = backup

        self._ipv4_gateway = ipv4_gateway

        if subnet_mask is None:
            # If no subnet mask is defined we assume a class C (24 bit) subnet
            subnet_mask = IPv4Address("255.255.255.0")
        self._subnet_mask = subnet_mask

        if 0 < lease_range[0] < 256 and 0 < lease_range[1] < 256 and lease_range[0] < lease_range[1]:
            ipv4_lease_range = (
                list(self.ipv4_network.hosts())[lease_range[0] - 1],
                list(self.ipv4_network.hosts())[lease_range[1] - 1],
            )
        else:
            logger.error(f"Outside valid lease range: {lease_range}")
            ipv4_lease_range = (list(self.ipv4_network.hosts())[0], list(self.ipv4_network.hosts())[-1])

        self._ipv4_lease_range = ipv4_lease_range

        self._lease_time = lease_time

        binary_path = shutil.which(self.binary_name())
        if binary_path is None:
            logger.error("Dnsmasq binary not found on system's PATH.")
            raise ValueError

        self._binary = pathlib.Path(binary_path)
        self.validate_binary()

        self.validate_config()
        asyncio.create_task(self.start())

    @staticmethod
    def binary_name() -> str:
        return "dnsmasq"

    def binary(self) -> pathlib.Path:
        return self._binary

    def validate_binary(self) -> None:
        if self.binary() is None:
            raise RuntimeError("Binary not available.")

        subprocess.check_output([self.binary(), "--test"])

    def validate_config(self) -> None:
        if not (self._ipv4_lease_range[0] in self.ipv4_network and self._ipv4_lease_range[1] in self.ipv4_network):
            raise ValueError("Initial and final DHCP lease addresses must be in the gateway/subnet network.")

        if not self._ipv4_lease_range[1] > self._ipv4_lease_range[0]:
            raise ValueError("Final DHCP lease address must be greater than the initial one.")

        subprocess.check_output([*self.command_list(), "--test"])

    def command_list(self) -> List[str]:
        """List of arguments to be used in the command line call.
        Refer to https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html for details about each argument."""

        return [
            self.binary().as_posix(),
            "--no-daemon",
            f"--interface={self._interface}",
            f"--dhcp-range={self._ipv4_lease_range[0]},{self._ipv4_lease_range[1]},{self._subnet_mask},{self._lease_time}",  # fmt: skip
            "--dhcp-option=option:router",
            "--bind-dynamic",
            "--dhcp-option=option6:information-refresh-time,6h",
            "--dhcp-rapid-commit",
            "--cache-size=1500",
            "--no-negcache",
            "--no-resolv",
            "--no-poll",
            "--port=0",
            "--user=root",
        ]

    async def start(self) -> None:
        if self._is_backup:
            servers_found = await discover_dhcp_servers(self._interface)
            if len(servers_found) > 0:
                logger.info(
                    f"Found {len(servers_found)} DHCP servers on the network. NOT starting DHCP server on interface {self._interface}."
                )
                return
        try:
            logger.info(f"Starting DHCP server on interface {self._interface}")
            logger.info("Command: " + " ".join(self.command_list()))
            # pylint: disable=consider-using-with
            self._subprocess = subprocess.Popen(self.command_list(), shell=False, encoding="utf-8", errors="ignore")
            await asyncio.sleep(3)
            if not self.is_running():
                exit_code = self._subprocess.returncode
                raise RuntimeError(f"Failed to initialize Dnsmasq ({exit_code}).")
            logger.info("DHCP Server started.")
        except Exception as error:
            raise RuntimeError("Unable to start DHCP Server.") from error

    def stop(self) -> None:
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
            logger.info("DHCP Server stopped.")
        else:
            logger.info("Tried to stop DHCP Server, but it was already not running.")

    async def restart(self) -> None:
        self.stop()
        await self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    @property
    def is_backup_server(self) -> bool:
        return self._is_backup

    @property
    def interface(self) -> str:
        return self._interface

    @property
    def ipv4_gateway(self) -> IPv4Address:
        return self._ipv4_gateway

    @property
    def ipv4_lease_range(self) -> tuple[IPv4Address, IPv4Address]:
        return self._ipv4_lease_range

    @property
    def ipv4_network(self) -> IPv4Network:
        return IPv4Interface(f"{self._ipv4_gateway}/{self._subnet_mask}").network

    def __del__(self) -> None:
        self.stop()
