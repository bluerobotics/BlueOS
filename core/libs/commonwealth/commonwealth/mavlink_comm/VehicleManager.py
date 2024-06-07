import asyncio
import math
from typing import Any, Dict, List

from loguru import logger

from commonwealth.mavlink_comm.config import DEFAULT_DATA_STREAMS_CONFIG
from commonwealth.mavlink_comm.exceptions import VehicleDisarmFail
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from commonwealth.mavlink_comm.typedefs import (
    FirmwareInfo,
    FirmwareVersionType,
    MavlinkMessageId,
    MavlinkVehicleType,
    MavDataStream,
)

MAV_MODE_FLAG_SAFETY_ARMED = 128


class VehicleManager:
    def __init__(self) -> None:
        self.mavlink2rest = MavlinkMessenger()

        self.target_system = 1
        self.target_component = 1
        self.confirmation = 0

    def set_target_system(self, target_system: int) -> None:
        logger.info(f"setting target system to: {target_system}")
        self.target_system = target_system

    def set_target_component(self, target_component: int) -> None:
        self.target_component = target_component

    def set_confirmation(self, confirmation: int) -> None:
        self.confirmation = confirmation

    def command_long_message(self, command_type: str, params: List[float]) -> Dict[str, Any]:
        return {
            "type": "COMMAND_LONG",
            "param1": params[0] if len(params) > 0 else 0,
            "param2": params[1] if len(params) > 1 else 0,
            "param3": params[2] if len(params) > 2 else 0,
            "param4": params[3] if len(params) > 3 else 0,
            "param5": params[4] if len(params) > 4 else 0,
            "param6": params[5] if len(params) > 5 else 0,
            "param7": params[6] if len(params) > 6 else 0,
            "command": {"type": command_type},
            "target_system": self.target_system,
            "target_component": self.target_component,
            "confirmation": self.confirmation,
        }

    def command_request_data_stream_message(
        self, stream: MavDataStream, interval_us: int = 0, disable: bool = False
    ) -> Dict[str, Any]:
        rate_hz = math.ceil(1e6 / interval_us) if interval_us > 0 else 0
        return {
            "type": "REQUEST_DATA_STREAM",
            "req_stream_id": int(stream.value),
            "start_stop": 0 if disable else 1,
            "req_message_rate": rate_hz,
            "target_system": self.target_system,
            "target_component": self.target_component,
        }

    def command_heartbeat_message(self) -> Dict[str, Any]:
        return {
            "type": "HEARTBEAT",
            "custom_mode": 0,
            "mavtype": {
                "type": "MAV_TYPE_GCS"
            },
            "autopilot": {
                "type": "MAV_AUTOPILOT_INVALID"
            },
            "base_mode": {
                "bits": 0
            },
            "system_status": {
                "type": "MAV_STATE_UNINIT"
            },
            "mavlink_version": 0,
        }

    async def request_data_stream(self, stream: MavDataStream, interval_us: int = 0, disable: bool = False) -> None:
        # Send old REQUEST_DATA_STREAM
        message = self.command_request_data_stream_message(stream, interval_us, not disable)
        await self.mavlink2rest.send_mavlink_message(message)
        # Send new MAV_CMD_SET_MESSAGE_INTERVAL if supported by the vehicle will allow precise control
        message = self.command_long_message("MAV_CMD_SET_MESSAGE_INTERVAL", [stream, -1 if disable else interval_us])
        await self.mavlink2rest.send_mavlink_message(message)

    async def send_heartbeat(self) -> None:
        message = self.command_heartbeat_message()
        await self.mavlink2rest.send_mavlink_message(message)

    async def init_default_stream_rates(self) -> None:
        # In case of PX4 we need to send a bunch of heartbeat messages first to open the communication
        logger.info("Trying to open communication with board.")
        for _ in range(20):
            logger.info("Sending heartbeat.")
            await self.send_heartbeat()
            await asyncio.sleep(0.1)

        logger.info("Started requesting default data streams.")

        for stream in DEFAULT_DATA_STREAMS_CONFIG:
            try:
                logger.info(f"Requesting stream {stream.stream} with interval {stream.interval_us} us.")
                await self.request_data_stream(stream.stream, stream.interval_us)
            except Exception as error:
                logger.error(f"Failed to request stream {stream.stream}. error: {error}")

        logger.info("Finished requesting default data streams")


    async def request_message(self, message_id: int) -> None:
        message = self.command_long_message("MAV_CMD_REQUEST_MESSAGE", [message_id])
        await self.mavlink2rest.send_mavlink_message(message)

    async def get_firmware_info(self) -> FirmwareInfo:
        request_message = self.command_long_message(
            "MAV_CMD_REQUEST_MESSAGE", [MavlinkMessageId.AUTOPILOT_VERSION.value]
        )
        await self.mavlink2rest.send_mavlink_message(request_message)
        try:
            autopilot_version = await self.mavlink2rest.get_mavlink_message(MavlinkMessageId.AUTOPILOT_VERSION.name)
            flight_sw_version_raw = autopilot_version["message"]["flight_sw_version"]
            major, minor, patch, version_type_raw = flight_sw_version_raw.to_bytes(4, byteorder="big")
            firmware_version = f"{major}.{minor}.{patch}"
            version_type = FirmwareVersionType.from_value(version_type_raw)
            return FirmwareInfo(version=firmware_version, type=version_type)

        except Exception as error:
            logger.error(f"Failed to request autopilot version. {error}")
            logger.info("trying to get a new system id")
            self.set_target_system(await self.mavlink2rest.get_most_recent_vehicle_id())
            raise ValueError("Failed to get autopilot version.") from Exception

    async def get_vehicle_type(self) -> MavlinkVehicleType:
        heartbeat_message = await self.mavlink2rest.get_updated_mavlink_message("HEARTBEAT")
        return MavlinkVehicleType[heartbeat_message["message"]["mavtype"]["type"]]  # type: ignore

    async def get_firmware_vehicle_type(self) -> str:
        vehicle_type = await self.get_vehicle_type()
        return vehicle_type.mavlink_firmware_type()

    async def reboot_vehicle(self) -> None:
        message = self.command_long_message("MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN", [1.0])
        await self.mavlink2rest.send_mavlink_message(message)

    async def shutdown_vehicle(self) -> None:
        shutdown_message = self.command_long_message("MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN", [2.0])
        await self.mavlink2rest.send_mavlink_message(shutdown_message)

    async def is_heart_beating(self) -> bool:
        try:
            await self.mavlink2rest.get_updated_mavlink_message("HEARTBEAT")
            return True
        except Exception as error:
            logger.error(f"Failed to check heartbeat. {error}")
            return False

    async def is_vehicle_armed(self) -> bool:
        get_response = await self.mavlink2rest.get_updated_mavlink_message("HEARTBEAT")
        base_mode_bits = get_response["message"]["base_mode"]["bits"]
        if not isinstance(base_mode_bits, int):
            raise ValueError("Got unexpected HEARTBEAT message from Autopilot.")

        # Check if bit representing an armed vehicle is on base_mode bit array
        return bool(base_mode_bits & MAV_MODE_FLAG_SAFETY_ARMED)

    async def disarm_vehicle(self) -> None:
        if not await self.is_vehicle_armed():
            logger.debug("Vehicle already disarmed.")
            return

        disarm_message = self.command_long_message("MAV_CMD_COMPONENT_ARM_DISARM", [])

        await self.mavlink2rest.send_mavlink_message(disarm_message)
        if await self.is_vehicle_armed():
            raise VehicleDisarmFail("Failed to disarm vehicle. Please try a manual disarm.")
