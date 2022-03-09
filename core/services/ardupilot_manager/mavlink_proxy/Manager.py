import asyncio
import pathlib
from typing import List, Optional, Set, Type

from loguru import logger

# Plugins
# pylint: disable=unused-import
import mavlink_proxy.MAVLinkRouter
import mavlink_proxy.MAVProxy
from exceptions import (
    EndpointCreationFail,
    EndpointDeleteFail,
    EndpointUpdateFail,
    NoMasterMavlinkEndpoint,
)
from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint


class Manager:
    def __init__(self) -> None:
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

    def add_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        for endpoint in new_endpoints:
            try:
                self.add_endpoint(endpoint)
            except Exception as error:
                self._reset_endpoints()
                raise EndpointCreationFail(
                    f"Failed adding endpoint '{endpoint.name}'. Endpoints reset to previous state."
                ) from error

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_remove))
        if protected_endpoints:
            raise ValueError(f"Endpoints {[e.name for e in protected_endpoints]} are protected. Aborting operation.")

        for endpoint in endpoints_to_remove:
            try:
                self.remove_endpoint(endpoint)
            except Exception as error:
                self._reset_endpoints()
                raise EndpointDeleteFail(
                    f"Failed removing endpoint '{endpoint.name}'. Endpoints reset to previous state."
                ) from error

    def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        old_endpoints = self.endpoints()

        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_update))
        if protected_endpoints:
            raise ValueError(f"Endpoints {[e.name for e in protected_endpoints]} are protected. Aborting operation.")

        for updated_endpoint in endpoints_to_update:
            old_endpoint = next((e for e in old_endpoints if e.name == updated_endpoint.name), None)
            try:
                if not old_endpoint:
                    raise ValueError(f"Endpoint '{updated_endpoint.name}' does not exist.")
                self.remove_endpoint(old_endpoint)
                self.add_endpoint(updated_endpoint)
            except Exception as error:
                self._reset_endpoints()
                raise EndpointUpdateFail(
                    f"Failed updating endpoint '{updated_endpoint.name}'. Endpoints reset to previous state."
                ) from error

    def endpoints(self) -> Set[Endpoint]:
        return self.tool.endpoints()

    def clear_endpoints(self) -> None:
        """Remove all output endpoints."""
        self.tool.clear_endpoints()

    def _reset_endpoints(self) -> None:
        self.clear_endpoints()
        self.add_endpoints(self._last_valid_endpoints)

    @property
    def master_endpoint(self) -> Optional[Endpoint]:
        return self.tool.master_endpoint

    def start(self, master_endpoint: Endpoint) -> None:
        self.should_be_running = True
        self.tool.start(master_endpoint)
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
        if self.master_endpoint is None:
            raise NoMasterMavlinkEndpoint("Mavlink master endpoint was not set. Cannot build command line.")
        return self.tool.assemble_command(self.master_endpoint)

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
