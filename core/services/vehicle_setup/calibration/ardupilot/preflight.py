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


def preflight_command(kind: CalibrationKind) -> Command:
    return Command(command=PREFLIGHT_CALIBRATION, params=list(PREFLIGHT_PARAMS[kind]))


def ack_outcome(message: Dict[str, Any], command: str) -> Optional[Tuple[CalibrationStatus, Optional[str]]]:
    """(status, failure reason) if `message` is the final COMMAND_ACK of `command`, None otherwise."""
    if message.get("type") != "COMMAND_ACK" or message.get("command", {}).get("type") != command:
        return None
    result = message.get("result", {}).get("type")
    if result == "MAV_RESULT_IN_PROGRESS":
        return None
    if result == "MAV_RESULT_ACCEPTED":
        return CalibrationStatus.DONE, None
    return CalibrationStatus.FAILED, f"{command} answered {result}"
