from enum import IntEnum, IntFlag
from typing import Any, Dict, Optional

import pynmea2
from pydantic import BaseModel

from nmea_injector.exceptions import UnsupportedSentenceType


class GPS_FIX_TYPE(IntEnum):
    GPS_FIX_TYPE_NO_GPS = 0
    GPS_FIX_TYPE_NO_FIX = 1
    GPS_FIX_TYPE_2D_FIX = 2
    GPS_FIX_TYPE_3D_FIX = 3
    GPS_FIX_TYPE_DGPS = 4
    GPS_FIX_TYPE_RTK_FLOAT = 5
    GPS_FIX_TYPE_RTK_FIXED = 6
    GPS_FIX_TYPE_STATIC = 7
    GPS_FIX_TYPE_PPP = 8


class GPS_INPUT_IGNORE_FLAG(IntFlag):
    GPS_INPUT_IGNORE_FLAG_ALT = 1
    GPS_INPUT_IGNORE_FLAG_HDOP = 2
    GPS_INPUT_IGNORE_FLAG_VDOP = 4
    GPS_INPUT_IGNORE_FLAG_VEL_HORIZ = 8
    GPS_INPUT_IGNORE_FLAG_VEL_VERT = 16
    GPS_INPUT_IGNORE_FLAG_SPEED_ACCURACY = 32
    GPS_INPUT_IGNORE_FLAG_HORIZONTAL_ACCURACY = 64
    GPS_INPUT_IGNORE_FLAG_VERTICAL_ACCURACY = 128


class Mavlink2RestBitEnum(BaseModel):
    bits: int


nmea_ignore_flags = (
    GPS_INPUT_IGNORE_FLAG.GPS_INPUT_IGNORE_FLAG_SPEED_ACCURACY
    | GPS_INPUT_IGNORE_FLAG.GPS_INPUT_IGNORE_FLAG_VEL_VERT
    | GPS_INPUT_IGNORE_FLAG.GPS_INPUT_IGNORE_FLAG_VEL_HORIZ
)


class MavlinkGpsInput(BaseModel):
    """Mavlink's package specification to input GPS data into stream (GPS_INPUT)."""

    type: str = "GPS_INPUT"
    time_usec: Optional[int] = 0
    gps_id: Optional[int] = 0
    ignore_flags: Optional[Mavlink2RestBitEnum] = Mavlink2RestBitEnum(bits=nmea_ignore_flags.value)
    time_week_ms: Optional[int] = 0
    time_week: Optional[int] = 0
    fix_type: Optional[int] = GPS_FIX_TYPE.GPS_FIX_TYPE_3D_FIX.value
    lat: int
    lon: int
    alt: Optional[float] = 0
    hdop: Optional[float] = 0
    vdop: Optional[float] = 0
    vn: Optional[float] = 0
    ve: Optional[float] = 0
    vd: Optional[float] = 0
    speed_accuracy: Optional[float] = 0
    horiz_accuracy: Optional[float] = 0
    vert_accuracy: Optional[float] = 0
    satellites_visible: Optional[int] = 0
    yaw: Optional[int] = 0


def parse_mavlink_from_sentence(msg: pynmea2.NMEASentence) -> MavlinkGpsInput:
    data: Dict[str, Any] = {}

    supported_sentence_types = ["GGA", "RMC", "GLL", "GNS"]
    if msg.sentence_type not in supported_sentence_types:
        raise UnsupportedSentenceType(f"Supported types are {supported_sentence_types}. Received {msg.sentence_type}")

    # Convert NMEA lat/long data from "float degrees" to "int degrees ^7"
    data["lat"] = int(msg.latitude * 1e7)
    data["lon"] = int(msg.longitude * 1e7)

    if msg.sentence_type == "GGA":
        data["hdop"] = float(msg.horizontal_dil)
        data["alt"] = float(msg.altitude)
        data["satellites_visible"] = int(msg.num_sats)
    elif msg.sentence_type == "GNS":
        data["hdop"] = float(msg.hdop)
        data["satellites_visible"] = int(msg.num_sats)

    return MavlinkGpsInput(**data)
