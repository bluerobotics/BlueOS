
import abc
from typing import List, Optional, Type

from loguru import logger

from autopilot.exceptions import InvalidEnvironmentImplementation
from autopilot.firmware import AutopilotFirmware
from flight_controller import FlightController
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.exceptions import EndpointAlreadyExists
from mavlink_proxy.Manager import Manager as MavlinkManager


class AutopilotEnvironment(abc.ABC):
    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.mavlink_manager: Optional[MavlinkManager] = None

    @classmethod
    def all(cls) -> List[str]:
        return [subclass.__name__ for subclass in cls.__subclasses__()]

    @classmethod
    def get(cls, name: str) -> Type["AutopilotEnvironment"]:
        for subclass in cls.__subclasses__():
            if subclass.__name__ == name:
                return subclass()
        raise InvalidEnvironmentImplementation(f"{name} is not a valid environment implementation class")

    async def start_mavlink_manager(self, device: Endpoint) -> None:
        default_endpoints = [
            Endpoint(
                name="GCS Server Link",
                owner=self.owner,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14550,
                persistent=True,
                enabled=False,
            ),
            Endpoint(
                name="GCS Client Link",
                owner=self.owner,
                connection_type=EndpointType.UDPClient,
                place="192.168.2.1",
                argument=14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                name="MAVLink2RestServer",
                owner=self.owner,
                connection_type=EndpointType.UDPServer,
                place="127.0.0.1",
                argument=14001,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="MAVLink2Rest",
                owner=self.owner,
                connection_type=EndpointType.UDPClient,
                place="127.0.0.1",
                argument=14000,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Internal Link",
                owner=self.owner,
                connection_type=EndpointType.TCPServer,
                place="127.0.0.1",
                argument=5777,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Ping360 Heading",
                owner=self.owner,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14660,
                persistent=True,
                protected=True,
            ),
        ]
        for endpoint in default_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except EndpointAlreadyExists:
                pass
            except Exception as error:
                logger.warning(str(error))
        await self.mavlink_manager.start(device)

    @abc.abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def restart(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def setup(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def boards(self, firmware: AutopilotFirmware) -> Optional[FlightController]:
        raise NotImplementedError
