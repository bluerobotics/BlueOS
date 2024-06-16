from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor


class Ping360EthernetDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor) -> None:
        super().__init__(ping, None)
