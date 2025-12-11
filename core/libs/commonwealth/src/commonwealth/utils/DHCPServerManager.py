import asyncio
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Any, List, Optional, Tuple

import psutil
from commonwealth.utils.DHCPDiscovery import discover_dhcp_servers
from loguru import logger
from pydantic import BaseModel


class DHCPServerLease(BaseModel):
    mac: str
    ip: IPv4Address
    expires_epoch: Optional[int] = None
    expires_at: Optional[datetime] = None
    hostname: Optional[str] = None
    client_id: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.expires_epoch > datetime.now(timezone.utc).timestamp() if self.expires_epoch else False


class DHCPServerDetails(BaseModel):
    interface: str
    ipv4_gateway: IPv4Address
    lease_range: Tuple[int, int]
    lease_time: str
    is_backup: bool
    is_running: bool
    leases: List[DHCPServerLease]
    subnet_mask: Optional[IPv4Address] = None


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
        lease_dir: pathlib.Path = pathlib.Path("/var/lib/dnsmasq"),
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

        lease_dir.mkdir(parents=True, exist_ok=True)
        self._lease_file = lease_dir.joinpath(f"dnsmasq-{self._interface}.leases")

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
            f"--dhcp-leasefile={self._lease_file}",
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

    def _parse_lease_line(self, line: str) -> Tuple[Optional[int], str, IPv4Address, Optional[str], Optional[str]]:
        # dnsmasq format:
        # <expiry_epoch> <mac> <ip> <hostname> <client_id>
        # hostname/client_id can be "*" or absent in odd cases

        parts = line.split()
        return (
            int(parts[0]) if parts[0].isdigit() else None,
            parts[1],
            IPv4Address(parts[2]),
            None if len(parts) >= 4 and parts[3] in ("*", "") else parts[3],
            None if len(parts) >= 5 and parts[4] in ("*", "") else parts[4],
        )

    def _get_valid_leases_lines(self, lines: List[str]) -> List[str]:
        return [line for line in lines if line.strip() and len(line.split()) >= 3]

    def _parse_leases_lines(self, lines: List[str]) -> List[DHCPServerLease]:
        out: List[DHCPServerLease] = []
        for line in self._get_valid_leases_lines(lines):
            try:
                expires_epoch, mac, ip, hostname, client_id = self._parse_lease_line(line)

                out.append(
                    DHCPServerLease(
                        expires_epoch=expires_epoch,
                        expires_at=datetime.fromtimestamp(expires_epoch, tz=timezone.utc) if expires_epoch else None,
                        mac=mac.lower(),
                        ip=ip,
                        hostname=hostname,
                        client_id=client_id,
                    )
                )
            except Exception as exc:
                logger.debug(f"Skipping malformed lease line '{line}': {exc}")
                continue
        return out

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

    @property
    def leases(self) -> List[DHCPServerLease]:
        """Return all parsed leases from this instance's lease file."""
        try:
            lines = self._lease_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except FileNotFoundError:
            return []
        except Exception as exc:
            logger.warning(f"Failed to read leases from {self._lease_file}: {exc}")
            return []

        return self._parse_leases_lines(lines)

    @property
    def details(self) -> DHCPServerDetails:
        return DHCPServerDetails(
            interface=self._interface,
            ipv4_gateway=self._ipv4_gateway,
            lease_range=self._ipv4_lease_range,
            lease_time=self._lease_time,
            is_backup=self._is_backup,
            is_running=self.is_running(),
            leases=self.leases,
            subnet_mask=self._subnet_mask,
        )

    def __del__(self) -> None:
        self.stop()
