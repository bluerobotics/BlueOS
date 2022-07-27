from ping1d_mavlink import Ping1DMavlinkDriver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor
from commonwealth.settings.manager import Manager
from settings import SettingsV1, Ping1dSettingsSpecV1
SERVICE_NAME = "ping"

class Ping1DDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)
        self.port = port

        # load settings
        self.manager = Manager(SERVICE_NAME, SettingsV1)
        settings = list(filter(lambda x: x.port == self.ping.port, self.manager.settings.ping1d_specs))
        if not settings:
            self.manager.settings.ping1d_specs.append(Ping1dSettingsSpecV1.new(self.ping.port.device, False))
        settings = list(filter(lambda x: x.port == self.ping.port.device, self.manager.settings.ping1d_specs))[0]
        self.manager.save()
        self.driver_status["mavlink_driver_enabled"] = settings.mavlink_enabled
        self.mavlink_driver = Ping1DMavlinkDriver(settings.mavlink_enabled)

    async def start(self) -> None:
        await super().start()
        await self.mavlink_driver.drive(self.port)

    def set_mavlink_driver_running(self, should_run: bool):
        self.mavlink_driver.set_should_run(should_run)
        self.driver_status["mavlink_driver_enabled"] = should_run
