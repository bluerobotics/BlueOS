import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from ipaddress import IPv4Address

from features.network import ClientPc, Lease
from targets.target import Target

logger = logging.getLogger(__name__)


class SilClientPcDriver(ClientPc):
    """Drives the client PC netns from targets/sil/image/router.nix"""

    def __init__(self, target: Target) -> None:
        self.target = target

    @contextmanager
    def connected(self) -> Iterator[Lease]:
        logger.info("connecting the client PC to the router")
        output = self._run(
            "timeout 120 dhcpcd --config /dev/null --nohook resolv.conf --nohook hostname --oneshot --ipv4only "
            "--noarp --nobackground client 2>&1"
        )
        ip, server = re.findall(r"(?:offered|acknowledged) ([\d.]+) from ([\d.]+)", output)[0]
        logger.info("client PC leased %s from %s", ip, server)
        try:
            yield Lease(IPv4Address(ip), IPv4Address(server))
        finally:
            logger.info("disconnecting the client PC %s", ip)
            self._run("ip addr flush dev client")
            self.target.shell("sudo rm -f /var/lib/dhcpcd/client.lease")

    def get(self, url: str) -> str:
        return self._run(f"curl -sS --fail {url}")

    def _run(self, command: str) -> str:
        return self.target.shell(f"sudo ip netns exec client {command}")
