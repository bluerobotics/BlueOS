from enum import Enum
from typing import Dict, List, Optional

from job_list.job import JobRef
from pydantic import BaseModel, Field, model_validator


# Ordered as ArduPilot's ACCELCAL_VEHICLE_POS 1 to 6
class PoseKey(str, Enum):
    LEVEL = "level"
    LEFT = "left"
    RIGHT = "right"
    NOSE_DOWN = "nose_down"
    NOSE_UP = "nose_up"
    BACK = "back"


class CalibrationStatus(str, Enum):
    RUNNING = "running"
    WAITING_FOR_POSITION = "waiting_for_position"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


FINISHED = (CalibrationStatus.DONE, CalibrationStatus.FAILED, CalibrationStatus.CANCELLED)


class Command(BaseModel):
    command: str
    params: List[float]


class CalibrationKind(str, Enum):
    GYROSCOPE = "gyroscope"
    BAROMETER = "barometer"
    ACCELEROMETER = "accelerometer"
    SIMPLE_ACCELEROMETER = "simple_accelerometer"
    BOARD_LEVEL = "board_level"
    COMPASS = "compass"
    LARGE_VEHICLE_COMPASS = "large_vehicle_compass"


class StartCalibration(BaseModel):
    calibration: CalibrationKind
    # ArduPilot's mask is a uint8
    compass_mask: Optional[int] = Field(default=None, ge=1, le=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def check_needed_fields(self) -> "StartCalibration":
        needed = {
            CalibrationKind.COMPASS: ("compass_mask",),
            CalibrationKind.LARGE_VEHICLE_COMPASS: ("compass_mask", "latitude", "longitude"),
        }.get(self.calibration, ())
        missing = [field for field in needed if getattr(self, field) is None]
        if missing:
            raise ValueError(f"{self.calibration.value} needs {', '.join(missing)}")
        return self


class ConfirmPosition(JobRef):
    pass


class CalibrationSession(BaseModel):
    job_id: str
    calibration: CalibrationKind
    status: CalibrationStatus
    position: Optional[PoseKey] = None
    progress: Optional[float] = None
    fitness: Dict[int, float] = {}
    reason: Optional[str] = None
    reboot_required: bool = False
