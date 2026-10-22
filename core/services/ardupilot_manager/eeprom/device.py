import os
import struct


class EEPROM:
    HAT_ID_MAGIC = b"R-Pi"

    # 4 bytes signature
    # 1 byte version
    # 1 byte reserved
    # 2 bytes numatoms
    # 4 bytes eeplen (little-endian)
    HAT_HEADER = struct.Struct("<4sBBHI")

    def __init__(self, path: str):
        self.path = path

    def size(self) -> int:
        return os.path.getsize(self.path)

    def read(self, offset: int, size: int) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(offset)
            return f.read(size)

    def write(self, offset: int, data: bytes) -> None:
        # Skip hat id partition if exists
        if offset < self.hat_id_partition_size():
            raise ValueError("Cannot write to hat id partition")
        if offset + len(data) > self.size():
            raise ValueError("Data does not fit in the EEPROM")
        with open(self.path, "r+b") as f:
            f.seek(offset)
            f.write(data)

    def has_hat_id(self) -> bool:
        return self.read(0, len(self.HAT_ID_MAGIC)) == self.HAT_ID_MAGIC

    def hat_id_partition_size(self) -> int:
        if not self.has_hat_id():
            return 0
        eeplen: int = self.HAT_HEADER.unpack(self.read(0, self.HAT_HEADER.size))[4]
        if not self.HAT_HEADER.size <= eeplen <= self.size():
            return self.size()
        return eeplen
