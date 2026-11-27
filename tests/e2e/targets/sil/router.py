import logging
from collections.abc import Iterator
from contextlib import contextmanager

from features.network import Router
from targets.target import Target

logger = logging.getLogger(__name__)


class SilRouterDriver(Router):
    """Drives the router container from targets/sil/image/router.nix"""

    def __init__(self, target: Target) -> None:
        self.target = target

    @contextmanager
    def without_dhcp_server(self) -> Iterator[None]:
        logger.info("stopping the router dhcp server")
        self._run("systemctl stop dnsmasq")
        try:
            yield
        finally:
            logger.info("starting the router dhcp server")
            self._run("systemctl start dnsmasq")

    def _run(self, command: str) -> str:
        return self.target.shell(f"sudo nixos-container run router -- {command}")
