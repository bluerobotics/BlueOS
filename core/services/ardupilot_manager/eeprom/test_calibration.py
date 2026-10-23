from eeprom.calibration import CalibrationDB, CalibrationRecord

PARAMS = {"INS_ACCOFFS_X": 0.5, "COMPASS_OFS2_Y": -12.25, "AHRS_TRIM_Z": 0.0}


def test_find_calibration_db() -> None:
    buffer = b"\xff" * 10 + CalibrationDB.from_params(PARAMS).to_bytes() + b"\xff" * 9
    database = CalibrationDB.find(buffer)
    assert database is not None
    assert database.offset == 10
    assert database.to_params() == PARAMS


def test_find_ignores_blank_buffer() -> None:
    assert CalibrationDB.find(b"\xff" * 64) is None


def test_invalid_crc_is_not_found() -> None:
    data = bytearray(CalibrationDB.from_params(PARAMS).to_bytes())
    data[-10] ^= 0xFF
    assert CalibrationDB.find(bytes(data)) is None


def test_params_that_are_not_calibrations_are_ignored() -> None:
    database = CalibrationDB.from_params({**PARAMS, "SERVO1_MIN": 1100.0})
    assert database.to_params() == PARAMS


def test_stored_names_that_are_not_calibrations_are_dropped() -> None:
    records = [CalibrationRecord("INS_ACCOFFS_X", 1.0), CalibrationRecord("SERVO1_MIN", 1100.0)]
    database = CalibrationDB.find(CalibrationDB(records).to_bytes())
    assert database is not None
    assert database.to_params() == {"INS_ACCOFFS_X": 1.0}
