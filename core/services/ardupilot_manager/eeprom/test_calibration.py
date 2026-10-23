from zlib import crc32

import pytest
from commonwealth.mavlink_comm.typedefs import MavlinkParameter, MavParamType
from eeprom.calibration import CalibrationDB, CalibrationRecord

REAL32 = MavParamType.MAV_PARAM_TYPE_REAL32
VALUES = {"INS_ACCOFFS_X": 0.5, "COMPASS_OFS2_Y": -12.25, "AHRS_TRIM_Z": 0.0}
PARAMS = {name: MavlinkParameter(type=REAL32, value=value) for name, value in VALUES.items()}
RECORD = CalibrationRecord("AHRS_TRIM_X", REAL32, 1.0).encode()


def pack_database(version: int, records: bytes) -> bytes:
    size = CalibrationDB.HEADER_LAYOUT.size + len(records) + CalibrationDB.CRC_LAYOUT.size
    body = CalibrationDB.HEADER_LAYOUT.pack(CalibrationDB.MAGIC, version, size) + records
    return body + CalibrationDB.CRC_LAYOUT.pack(crc32(body))


def test_find_calibration_db() -> None:
    buffer = b"\xff" * 10 + CalibrationDB.from_params(PARAMS).to_bytes() + b"\xff" * 9
    database = CalibrationDB.find(buffer)
    assert database is not None
    assert database.offset == 10
    assert database.to_params() == VALUES


def test_find_ignores_blank_buffer() -> None:
    assert CalibrationDB.find(b"\xff" * 64) is None


def test_invalid_crc_is_not_found() -> None:
    data = bytearray(CalibrationDB.from_params(PARAMS).to_bytes())
    data[-10] ^= 0xFF
    assert CalibrationDB.find(bytes(data)) is None


def test_params_that_are_not_calibrations_are_ignored() -> None:
    other = MavlinkParameter(type=MavParamType.MAV_PARAM_TYPE_INT16, value=1100)
    database = CalibrationDB.from_params({**PARAMS, "SERVO1_MIN": other})
    assert database.to_params() == VALUES


def test_stored_names_that_are_not_calibrations_are_dropped() -> None:
    records = [CalibrationRecord("INS_ACCOFFS_X", REAL32, 1.0), CalibrationRecord("SERVO1_MIN", REAL32, 1100.0)]
    database = CalibrationDB.find(CalibrationDB(records).to_bytes())
    assert database is not None
    assert database.to_params() == {"INS_ACCOFFS_X": 1.0}


@pytest.mark.parametrize(
    "param_type, value",
    [
        (MavParamType.MAV_PARAM_TYPE_UINT8, 2**8 - 1),
        (MavParamType.MAV_PARAM_TYPE_INT8, -(2**7)),
        (MavParamType.MAV_PARAM_TYPE_UINT16, 2**16 - 1),
        (MavParamType.MAV_PARAM_TYPE_INT16, -(2**15)),
        (MavParamType.MAV_PARAM_TYPE_UINT32, 2**32 - 1),
        (MavParamType.MAV_PARAM_TYPE_INT32, -(2**31)),
        (MavParamType.MAV_PARAM_TYPE_UINT64, 2**64 - 1),
        (MavParamType.MAV_PARAM_TYPE_INT64, -(2**63)),
        (MavParamType.MAV_PARAM_TYPE_REAL32, -12.25),
        (MavParamType.MAV_PARAM_TYPE_REAL64, 0.1),
    ],
)
def test_every_param_type_survives_the_round_trip(param_type: MavParamType, value: int | float) -> None:
    record = CalibrationRecord("AHRS_TRIM_X", param_type, value)
    assert CalibrationRecord.decode(record.encode()) == record


def test_cast_follows_param_type() -> None:
    assert isinstance(MavParamType.MAV_PARAM_TYPE_INT32.cast(3.0), int)
    assert isinstance(MavParamType.MAV_PARAM_TYPE_REAL32.cast(3), float)


def test_pack_database_matches_the_real_format() -> None:
    database = CalibrationDB([CalibrationRecord("AHRS_TRIM_X", REAL32, 1.0)])
    assert pack_database(CalibrationDB.CURRENT_VERSION, RECORD) == database.to_bytes()


def test_truncated_database_is_not_found() -> None:
    data = CalibrationDB.from_params(PARAMS).to_bytes()
    for size in range(len(data)):
        assert CalibrationDB.find(data[:size]) is None


def test_wrong_magic_is_not_found() -> None:
    data = CalibrationDB.from_params(PARAMS).to_bytes()
    assert CalibrationDB.find(b"XXXX" + data[len(CalibrationDB.MAGIC) :]) is None


def test_partial_record_is_not_found() -> None:
    data = pack_database(CalibrationDB.CURRENT_VERSION, RECORD + b"\0")
    assert CalibrationDB.find(data) is None


def test_unknown_param_type_is_not_found() -> None:
    record = CalibrationRecord.layout.pack(b"AHRS_TRIM_X", 99, bytes(8))
    assert CalibrationDB.find(pack_database(CalibrationDB.CURRENT_VERSION, record)) is None


def test_valid_database_is_found_after_a_corrupted_one() -> None:
    valid = CalibrationDB.from_params(PARAMS).to_bytes()
    corrupted = bytearray(valid)
    corrupted[-1] ^= 0xFF
    database = CalibrationDB.find(bytes(corrupted) + valid)
    assert database is not None
    assert database.offset == len(valid)


def test_newer_version_is_ignored() -> None:
    assert CalibrationDB.find(pack_database(CalibrationDB.CURRENT_VERSION + 1, RECORD)) is None
