from typing import List, Type
from warnings import warn

# Plugins
# pylint: disable=unused-import
import mavlink_proxy.MAVLinkRouter
import mavlink_proxy.MAVProxy
from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint


class Manager:
    def __init__(self) -> None:
        self.master: Endpoint
        if not Manager.available_interfaces():
            raise RuntimeError(
                "No MAVLink routers found,"
                " make sure that at least one is installed."
                f" Supported: {Manager.possible_interfaces()}"
            )

        self.tool = Manager.available_interfaces()[0]()

    @staticmethod
    def possible_interfaces() -> List[str]:
        return AbstractRouter.possible_interfaces()

    @staticmethod
    def available_interfaces() -> List[Type[AbstractRouter]]:
        return AbstractRouter.available_interfaces()

    def use(self, interface: AbstractRouter) -> None:
        self.tool = interface

    def add_endpoint(self, endpoint: Endpoint) -> bool:
        return self.tool.add_endpoint(endpoint)

    def remove_endpoint(self, endpoint: Endpoint) -> bool:
        return self.tool.remove_endpoint(endpoint)

    def add_endpoints(self, endpoints: List[Endpoint]) -> None:
        for endpoint in endpoints:
            if not self.add_endpoint(endpoint):
                warn(f"Endpoint {endpoint} is not valid.", RuntimeWarning)

    def remove_endpoints(self, endpoints: List[Endpoint]) -> None:
        for endpoint in endpoints:
            if not self.remove_endpoint(endpoint):
                warn(f"Endpoint {endpoint} is not valid.", RuntimeWarning)

    def endpoints(self) -> List[Endpoint]:
        return self.tool.endpoints()

    def set_master_endpoint(self, master: Endpoint) -> None:
        self.master = master

    def start(self) -> None:
        self.tool.start(self.master)

    def restart(self) -> bool:
        return self.tool.restart()

    def command_line(self) -> str:
        if not self.master:
            raise RuntimeError("Master endpoint was not defined.")

        return self.tool.assemble_command(self.master)

    def is_running(self) -> bool:
        return self.tool.is_running()
