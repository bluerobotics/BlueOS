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
    def without_internet(self) -> Iterator[None]:
        logger.info("cutting the router internet")
        self._run("iptables -I FORWARD -i br0 -j DROP")
        try:
            yield
        finally:
            logger.info("restoring the router internet")
            self._run("iptables -D FORWARD -i br0 -j DROP")

    @contextmanager
    def without_dhcp_server(self) -> Iterator[None]:
        logger.info("stopping the router dhcp server")
        self._run("systemctl stop dnsmasq")
        try:
            yield
        finally:
            logger.info("starting the router dhcp server")
            self._run("systemctl start dnsmasq")

    @contextmanager
    def without_vehicle_cable(self) -> Iterator[None]:
        # Taking the router's end of the veth down drops the carrier of the VM's eth0
        logger.info("unplugging the vehicle cable")
        self._run("ip link set eth0 down")
        try:
            yield
        finally:
            logger.info("plugging the vehicle cable back")
            self._run("ip link set eth0 up")

    def _run(self, command: str) -> str:
        return self.target.shell(f"sudo nixos-container run router -- {command}")
