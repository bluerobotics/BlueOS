import asyncio
from typing import Any, Dict

import pytest
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from commonwealth.mavlink_comm.VehicleManager import VehicleManager


class FakeMavlinkMessenger:
    def __init__(self, base_mode: Any) -> None:
        self.base_mode = base_mode

    async def get_updated_mavlink_message(self, _message_name: str) -> Dict[str, Any]:
        return {"message": {"base_mode": self.base_mode}}


def is_armed(base_mode: Any) -> bool:
    manager = VehicleManager()
    manager.mavlink2rest = FakeMavlinkMessenger(base_mode)  # type: ignore[assignment]
    return asyncio.run(manager.is_vehicle_armed())


def test_outgoing_messages_use_mavlink2rest_1_string_fields() -> None:
    assert VehicleManager().command_heartbeat_message()["base_mode"] == ""
    assert MavlinkMessenger().command_statustext_message("Ready")["text"] == "Ready"


def test_armed_state_accepts_old_and_new_mavlink2rest_flags() -> None:
    assert is_armed({"bits": 128})
    assert not is_armed({"bits": 0})
    assert is_armed("MAV_MODE_FLAG_MANUAL_INPUT_ENABLED | MAV_MODE_FLAG_SAFETY_ARMED")
    assert not is_armed("MAV_MODE_FLAG_MANUAL_INPUT_ENABLED")


def test_armed_state_rejects_unknown_flag_shapes() -> None:
    with pytest.raises(ValueError, match="unexpected HEARTBEAT"):
        is_armed(["MAV_MODE_FLAG_SAFETY_ARMED"])
