import os
from enum import IntEnum

from commonwealth.mavlink_comm.VehicleManager import VehicleManager

from .calibration import CalibrationDB
from .device import EEPROM


class Status(IntEnum):
    EEPROM_NOT_FOUND = 0
    READ_ONLY = 1
    VALID = 2


class EEPROMManager:
    EEPROM_PATH = os.environ.get("BLUEOS_EEPROM_PATH", "/sys/bus/i2c/devices/0-0050/eeprom")

    def __init__(self) -> None:
        self.eeprom = EEPROM(self.EEPROM_PATH)
        self.vehicle_manager = VehicleManager()

    def status(self) -> Status:
        if not os.path.exists(self.EEPROM_PATH):
            return Status.EEPROM_NOT_FOUND
        if not os.access(self.EEPROM_PATH, os.W_OK):
            return Status.READ_ONLY
        return Status.VALID

    def read_calibration(self) -> CalibrationDB | None:
        return CalibrationDB.find(self.eeprom.read(0, self.eeprom.size()))

    def dump(self) -> bytes:
        return self.eeprom.read(0, self.eeprom.size())

    async def backup(self) -> dict[str, float]:
        if not await self.vehicle_manager.is_heart_beating():
            raise RuntimeError("MAVLink is not available")
        calibration = CalibrationDB.from_params(await self.vehicle_manager.get_all_parameters())
        if not calibration.calibration_records:
            raise RuntimeError("No parameters received from the autopilot")
        existing = self.read_calibration()
        # Override the existing backup, otherwise create it after the hat id partition
        offset = self.eeprom.hat_id_partition_size()
        if existing and existing.offset is not None:
            offset = existing.offset
        self.eeprom.write(offset, calibration.to_bytes())
        return calibration.to_params()
