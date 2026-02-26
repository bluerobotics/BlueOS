import asyncio
from pathlib import Path

from bridges.bridges import Bridge
from bridges.serialhelper import Baudrate
from commonwealth.settings.manager import PydanticManager
from loguru import logger
from ping1d_mavlink import Ping1DMavlinkDriver
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor
from settings import Ping1dSettingsSpecV1, SettingsV1

SERVICE_NAME = "ping"

USERDATA = Path("/usr/blueos/userdata/")


class Ping1DDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)
        # load settings
        self.manager: PydanticManager = PydanticManager(SERVICE_NAME, SettingsV1, USERDATA / "settings" / SERVICE_NAME)
        # our settings file is a list for each sensor type.
        # check the list to find our current sensor in it
        connection_info = self.ping.get_hw_or_eth_info()
        settings = [ping1d for ping1d in self.manager.settings.ping1d_specs if ping1d.port == connection_info]
        # if it is not there, we create a new entry
        if not settings:
            self.manager.settings.ping1d_specs.append(Ping1dSettingsSpecV1.new(connection_info, False))
            self.manager.save()
        # read settings again, and extract first (and only) result
        (our_settings,) = [ping1d for ping1d in self.manager.settings.ping1d_specs if ping1d.port == connection_info]
        self.driver_status.mavlink_driver_enabled = our_settings.mavlink_enabled
        self.mavlink_driver = Ping1DMavlinkDriver(our_settings.mavlink_enabled)

    async def start(self) -> None:
        await super().start()
        # self.port shouldn't be None, as we force port to Int in the constructor
        # the following assert makes mypy happy
        assert self.port is not None, "Ping1d port is None."
        while True:
            try:
                logger.info("trying to start mavlink driver")
                await self.mavlink_driver.drive(self.port)
            except Exception as error:
                logger.warning(error)
                assert self.bridge is not None
                self.bridge.stop()
                await asyncio.sleep(5)
                baudrate = Baudrate.b115200 if self.baud is None else self.baud
                self.bridge = Bridge(self.ping.port, baudrate, "0.0.0.0", 0, self.port, automatic_disconnect=False)

    def save_settings(self) -> None:
        self.manager.load()  # re-load as other sensors could have changed it
        new_setting_item = Ping1dSettingsSpecV1.new(self.ping.get_hw_or_eth_info(), self.mavlink_driver.should_run)
        old_settings = self.manager.settings.ping1d_specs
        # generate a new list replacing our item
        new_settings = [
            setting if setting.port != self.ping.get_hw_or_eth_info() else new_setting_item for setting in old_settings
        ]
        self.manager.settings.ping1d_specs = new_settings
        self.manager.save()

    def set_mavlink_driver_running(self, should_run: bool) -> None:
        self.mavlink_driver.set_should_run(should_run)
        self.driver_status.mavlink_driver_enabled = should_run
        self.save_settings()
