import asyncio
import pathlib
from typing import List, Set, Type

from loguru import logger

# Plugins
# pylint: disable=unused-import
import mavlink_proxy.MAVLinkRouter
import mavlink_proxy.MAVProxy
from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint


class Manager:
    def __init__(self) -> None:
        self.master: Endpoint
        available_interfaces = Manager.available_interfaces()
        if not available_interfaces:
            raise RuntimeError(
                "No MAVLink routers found,"
                " make sure that at least one is installed."
                f" Supported: {Manager.possible_interfaces()}"
            )

        self.tool = available_interfaces[0]()
        self.should_be_running = False
        self._last_valid_endpoints: Set[Endpoint] = set()

    @staticmethod
    def possible_interfaces() -> List[str]:
        return AbstractRouter.possible_interfaces()

    @staticmethod
    def available_interfaces() -> List[Type[AbstractRouter]]:
        return AbstractRouter.available_interfaces()

    def use(self, interface: AbstractRouter) -> None:
        self.tool = interface

    def add_endpoint(self, endpoint: Endpoint) -> None:
        self.tool.add_endpoint(endpoint)

    def remove_endpoint(self, endpoint: Endpoint) -> None:
        self.tool.remove_endpoint(endpoint)

    def add_endpoints(self, endpoints: Set[Endpoint]) -> None:
        for endpoint in endpoints:
            self.add_endpoint(endpoint)

    def remove_endpoints(self, endpoints: Set[Endpoint]) -> None:
        for endpoint in endpoints:
            self.remove_endpoint(endpoint)

    def endpoints(self) -> Set[Endpoint]:
        return self.tool.endpoints()

    def clear_endpoints(self) -> None:
        """Remove all output endpoints."""
        self.tool.clear_endpoints()

    def reset_endpoints(self) -> None:
        self.clear_endpoints()
        self.add_endpoints(self._last_valid_endpoints)

    def set_master_endpoint(self, master: Endpoint) -> None:
        self.master = master

    def start(self) -> None:
        self.should_be_running = True
        self.tool.start(self.master)
        self._last_valid_endpoints = self.endpoints()

    def stop(self) -> None:
        self.should_be_running = False
        self.tool.exit()

    def restart(self) -> None:
        self.should_be_running = False
        self.tool.restart()
        self._last_valid_endpoints = self.endpoints()
        self.should_be_running = True

    def command_line(self) -> str:
        if not self.master:
            raise RuntimeError("Master endpoint was not defined.")

        return self.tool.assemble_command(self.master)

    def is_running(self) -> bool:
        return self.tool.is_running()

    def router_name(self) -> str:
        return self.tool.name()

    def set_logdir(self, log_dir: pathlib.Path) -> None:
        self.tool.set_logdir(log_dir)

    async def auto_restart_router(self) -> None:
        """Auto-restart Mavlink router process if it dies."""
        while True:
            await asyncio.sleep(5.0)

            needs_restart = self.should_be_running and not self.is_running()

            if not needs_restart:
                continue

            logger.debug("Mavlink router stopped. Trying to restart it.")
            try:
                self.restart()
                logger.debug("Mavlink router successfully restarted.")
            except Exception as error:
                logger.error(f"Failed to restart Mavlink router. {error}")

            self.should_be_running = True
