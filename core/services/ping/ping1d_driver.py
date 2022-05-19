from ping1d_mavlink import drive
from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor


class Ping1DDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)
        self.port = port

    async def start(self) -> None:
        await super().start()
        await drive(self.port)
