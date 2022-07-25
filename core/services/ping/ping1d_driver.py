from ping1d_mavlink import Ping1DMavlinkDriver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor


class Ping1DDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)
        self.port = port
        self.mavlink_driver = Ping1DMavlinkDriver()

    async def start(self) -> None:
        await super().start()
        await self.mavlink_driver.drive(self.port)

    def set_mavlink_driver_running(self, should_run: bool):
        self.mavlink_driver.set_should_run(should_run)