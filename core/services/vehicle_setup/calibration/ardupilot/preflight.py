from typing import Any, Dict, Optional, Tuple

from vehicle_setup_types import CalibrationKind, CalibrationStatus, Command

PREFLIGHT_CALIBRATION = "MAV_CMD_PREFLIGHT_CALIBRATION"

# https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_CALIBRATION
PREFLIGHT_PARAMS: Dict[CalibrationKind, Tuple[float, ...]] = {
    CalibrationKind.GYROSCOPE: (1, 0, 0, 0, 0, 0, 0),
    CalibrationKind.BAROMETER: (0, 0, 1, 0, 0, 0, 0),
    CalibrationKind.ACCELEROMETER: (0, 0, 0, 0, 1, 0, 0),
    CalibrationKind.BOARD_LEVEL: (0, 0, 0, 0, 2, 0, 0),
    CalibrationKind.SIMPLE_ACCELEROMETER: (0, 0, 0, 0, 4, 0, 0),
}


# https://mavlink.io/en/messages/common.html#MAV_RESULT
FAILED_RESULTS = (
    "MAV_RESULT_TEMPORARILY_REJECTED",
    "MAV_RESULT_DENIED",
    "MAV_RESULT_UNSUPPORTED",
    "MAV_RESULT_FAILED",
    "MAV_RESULT_CANCELLED",
    "MAV_RESULT_COMMAND_LONG_ONLY",
    "MAV_RESULT_COMMAND_INT_ONLY",
    "MAV_RESULT_COMMAND_UNSUPPORTED_MAV_FRAME",
    "MAV_RESULT_NOT_IN_CONTROL",
)


def preflight_command(kind: CalibrationKind) -> Command:
    return Command(command=PREFLIGHT_CALIBRATION, params=list(PREFLIGHT_PARAMS[kind]))


def unknown(what: str) -> str:
    return f"{what}, which this version of BlueOS doesn't know"


def ack_outcome(message: Dict[str, Any], command: str) -> Optional[Tuple[CalibrationStatus, Optional[str]]]:
    """(status, failure reason) if `message` is the final COMMAND_ACK of `command`, None otherwise."""
    if message.get("type") != "COMMAND_ACK" or message.get("command", {}).get("type") != command:
        return None
    result = message.get("result", {}).get("type")
    if result == "MAV_RESULT_IN_PROGRESS":
        return None
    if result == "MAV_RESULT_ACCEPTED":
        return CalibrationStatus.DONE, None
    if result in FAILED_RESULTS:
        return CalibrationStatus.FAILED, f"{command} answered {result}"
    return CalibrationStatus.UNKNOWN, unknown(f"{command} answered {result}")
