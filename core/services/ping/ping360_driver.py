from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor


class Ping360Driver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)
