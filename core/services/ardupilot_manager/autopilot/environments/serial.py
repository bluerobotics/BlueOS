from typing import Optional
from autopilot.environment import AutopilotEnvironment
from autopilot.firmware import AutopilotFirmware
from flight_controller import FlightController
from mavlink_proxy.Endpoint import Endpoint, EndpointType

class SerialEnvironment(AutopilotEnvironment):
    def __init__(self, owner: str, board: FlightController) -> None:
        self.board: FlightController = board
        super().__init__(owner)

    async def start(self) -> None:
        if not self.board.path:
            raise ValueError(f"Could not find device path for board {self.board.name}.")

        baudrate = 115200
        is_px4 = "px4" in self.board.name.lower()
        if is_px4:
            baudrate = 57600
        await self.start_mavlink_manager(
            Endpoint(
                name="Master",
                owner=self.owner,
                connection_type=EndpointType.Serial,
                place=self.board.path,
                argument=baudrate,
                protected=True,
            )
        )
        if is_px4:
            # PX4 needs at least one initial heartbeat to start sending data
            await self.vehicle_manager.burst_heartbeat()

    def stop(self) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        raise NotImplementedError

    def setup(self) -> None:
        raise NotImplementedError

    def boards(self, firmware: AutopilotFirmware) -> Optional[FlightController]:
        raise NotImplementedError
