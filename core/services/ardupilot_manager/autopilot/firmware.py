from typing import List, Optional, Type

from autopilot.exceptions import InvalidFirmwareImplementation
from flight_controller import FlightController


class AutopilotFirmware:
    @classmethod
    def all(cls) -> List[str]:
        return [subclass.__name__ for subclass in cls.__subclasses__()]

    @classmethod
    def get(cls, name: str) -> Optional[Type["AutopilotFirmware"]]:
        for subclass in cls.__subclasses__():
            if subclass.__name__ == name:
                return subclass()
        raise InvalidFirmwareImplementation(f"{name} is not a valid firmware implementation class")

    def supported_boards(self) -> List[FlightController]:
        raise NotImplementedError
