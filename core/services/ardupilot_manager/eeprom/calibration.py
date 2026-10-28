import re
import struct
from dataclasses import dataclass
from typing import ClassVar, Self
from zlib import crc32

CALIBRATION_PARAM = re.compile(
    r"""
    ^(
        INS_ACC[23]?(OFFS|SCAL)     # accelerometer offsets and scale, sensors 1 to 3
        | INS_GYR(OFFS|[23]OFFS)    # gyroscope offsets, sensors 1 to 3
        | COMPASS_(OFS|DIA|ODI)[23]?  # compass offsets, diagonals and off-diagonals, sensors 1 to 3
        | AHRS_TRIM                 # board level trim
    )_[XYZ]$                        # axis
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class CalibrationRecord:
    layout: ClassVar[struct.Struct] = struct.Struct(">16sf")
    name: str
    value: float

    def encode(self) -> bytes:
        return self.layout.pack(self.name.encode(), self.value)

    @classmethod
    def decode(cls, data: bytes) -> Self:
        name, value = cls.layout.unpack_from(data)
        return cls(name.rstrip(b"\0").decode(errors="replace"), value)

    @classmethod
    def size(cls) -> int:
        return cls.layout.size


class CalibrationDB:
    MAGIC: ClassVar[bytes] = b"BCAL"
    # Versions higher than this are not supported
    CURRENT_VERSION: ClassVar[int] = 1

    # MAGIC: 4 bytes
    # VERSION: 1 byte
    # SIZE: 4 bytes, the whole buffer including the header and the crc
    HEADER_LAYOUT: ClassVar[struct.Struct] = struct.Struct(">4sBI")
    CRC_LAYOUT: ClassVar[struct.Struct] = struct.Struct(">I")

    def __init__(self, calibration_records: list[CalibrationRecord], offset: int | None = None):
        self.calibration_records = calibration_records
        self.offset = offset

    @classmethod
    def from_params(cls, params: dict[str, float]) -> Self:
        return cls([CalibrationRecord(name, value) for name, value in params.items() if CALIBRATION_PARAM.match(name)])

    def to_params(self) -> dict[str, float]:
        return {record.name: record.value for record in self.calibration_records}

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self | None:
        if len(buffer) < cls.HEADER_LAYOUT.size:
            return None
        magic, version, size = cls.HEADER_LAYOUT.unpack_from(buffer)
        if magic != cls.MAGIC or version != cls.CURRENT_VERSION:
            return None
        if not cls.HEADER_LAYOUT.size + cls.CRC_LAYOUT.size <= size <= len(buffer):
            return None
        body_size = size - cls.CRC_LAYOUT.size
        if cls.CRC_LAYOUT.unpack_from(buffer, body_size)[0] != crc32(buffer[:body_size]):
            return None
        record_size = CalibrationRecord.size()
        if (body_size - cls.HEADER_LAYOUT.size) % record_size != 0:
            return None
        records = [
            CalibrationRecord.decode(buffer[position : position + record_size])
            for position in range(cls.HEADER_LAYOUT.size, body_size, record_size)
        ]
        return cls([record for record in records if CALIBRATION_PARAM.match(record.name)])

    def to_bytes(self) -> bytes:
        records = b"".join(record.encode() for record in self.calibration_records)
        size = self.HEADER_LAYOUT.size + len(records) + self.CRC_LAYOUT.size
        body = self.HEADER_LAYOUT.pack(self.MAGIC, self.CURRENT_VERSION, size) + records
        return body + self.CRC_LAYOUT.pack(crc32(body))

    @classmethod
    def find(cls, buffer: bytes) -> Self | None:
        offset = buffer.find(cls.MAGIC)
        while offset != -1:
            db = cls.from_bytes(buffer[offset:])
            if db is not None:
                db.offset = offset
                return db
            offset = buffer.find(cls.MAGIC, offset + 1)
        return None
