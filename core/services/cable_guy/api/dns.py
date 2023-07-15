import ipaddress
from typing import List

from commonwealth.utils.commands import run_command
from commonwealth.utils.decorators import temporary_cache
from loguru import logger
from pydantic import BaseModel

RESOLVCONF_FILE_PATH: str = "/etc/resolv.conf"


class DnsData(BaseModel):
    nameservers: List[str]
    lock: bool


class Dns:
    @staticmethod
    @temporary_cache(timeout_seconds=1)
    def retrieve_host_nameservers() -> DnsData:
        """Retrieve the host's DNS configuration from `/etc/resolv.conf`"""
        logger.debug(f"Retrieving DNS configuration from host {RESOLVCONF_FILE_PATH}...")

        resolvconf_content = Dns._retrieve_host_file_content(RESOLVCONF_FILE_PATH)
        is_locked = Dns._check_lock_host_file(RESOLVCONF_FILE_PATH)
        nameservers = Dns._deserialize_resolvconf_content(resolvconf_content)

        # Ignore invalid nameservers
        nameservers = [nameserver for nameserver in nameservers if Dns._validate_nameserver(nameserver)]

        return DnsData(nameservers=nameservers, lock=is_locked)

    @staticmethod
    def update_host_nameservers(dns_data: DnsData) -> None:
        """Update the host's DNS configuration from `/etc/resolv.conf`"""
        nameservers = dns_data.nameservers
        lock = dns_data.lock

        # Error if any invalid nameserver
        for nameserver in nameservers:
            if Dns._validate_nameserver(nameserver) is False:
                raise ValueError("Invalid nameserver provided")

        logger.debug(f"Updating DNS configuration from host {RESOLVCONF_FILE_PATH} w/ nameservers: {nameservers}")

        resolvconf_content = Dns._serialize_resolvconf_content(nameservers)
        Dns._unlock_host_file(RESOLVCONF_FILE_PATH)
        Dns._update_host_file_content(RESOLVCONF_FILE_PATH, resolvconf_content)
        if lock:
            Dns._lock_host_file(RESOLVCONF_FILE_PATH)

        logger.debug("Successfully updated the DNS configuration")

    @staticmethod
    def _retrieve_host_file_content(filename: str) -> str:
        output = run_command(f"cat '{filename}'")
        if output.returncode != 0:
            raise RuntimeError(f"Failed to read {filename} from the host: {output.stderr}")

        return str(output.stdout)

    @staticmethod
    def _check_lock_host_file(filename: str) -> bool:
        output = run_command(f"lsattr {filename}")
        if output.returncode != 0:
            raise RuntimeError(f"Failed to read the lock of file {filename} on the host: {output.stderr}")

        file_attributes = list(output.stdout.split()[0])
        is_locked = "i" in file_attributes
        return is_locked

    @staticmethod
    def _lock_host_file(filename: str) -> None:
        output = run_command(f"sudo chattr +i {filename}")
        if output.returncode != 0:
            raise RuntimeError(f"Failed to unlock the file {filename} on the host: {output.stderr}")

    @staticmethod
    def _unlock_host_file(filename: str) -> None:
        output = run_command(f"sudo chattr -i {filename}")
        if output.returncode != 0:
            raise RuntimeError(f"Failed to unlock the file {filename} on the host: {output.stderr}")

    @staticmethod
    def _update_host_file_content(filename: str, content: str) -> None:
        output = run_command(f"echo '{content}' | sudo tee {filename}")
        if output.returncode != 0:
            raise RuntimeError(f"Failed to update {filename} on the host: {output.stderr}")

    @staticmethod
    def _serialize_resolvconf_content(nameservers: List[str]) -> str:
        return "\n".join([f"nameserver {nameserver}" for nameserver in nameservers]) + "\n"

    @staticmethod
    def _deserialize_resolvconf_content(resolvconf_content: str) -> List[str]:
        return [line.lstrip().split()[-1] for line in resolvconf_content.split("\n") if line.startswith("nameserver ")]

    @staticmethod
    def _validate_nameserver(nameserver: str) -> bool:
        try:
            ipaddress.ip_address(nameserver)
        except ValueError as e:
            logger.warning(f"Invalid nameserver: {nameserver}: {e}")
            return False

        return True
