from typing import List

from pingdriver import PingDriver
from pingutils import PingDeviceDescriptor
from serialhelper import Baudrates

# TODO: make this a setting once we have a proper settings library
MAX_PING1D_BAUDRATE = Baudrates.b115200


class Ping1DDriver(PingDriver):
    def __init__(self, ping: PingDeviceDescriptor, port: int) -> None:
        super().__init__(ping, port)

    @staticmethod
    def baudrate_candidates() -> List[Baudrates]:
        """
        returns a list of baudrates to probe this sensor for
        """
        return list(filter(lambda x: x.value <= MAX_PING1D_BAUDRATE, Baudrates))
