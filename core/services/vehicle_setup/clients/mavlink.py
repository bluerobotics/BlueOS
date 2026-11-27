import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

import zenoh
from calibration.job import Connect, Connected, Heard, Send
from commonwealth.jobs.bus import open_session
from commonwealth.jobs.job import Io
from commonwealth.mavlink_comm.typedefs import MavlinkVehicleType
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from config import SERVICE_NAME

AUTOPILOT_COMPONENT_ID = 1
AUTOPILOT_MESSAGES = ("COMMAND_ACK", "COMMAND_LONG", "MAG_CAL_PROGRESS", "MAG_CAL_REPORT")

# mavlink-server's zenoh endpoint puts each message on mavlink/<system>/<component>/<NAME> and sends what's put here
SEND_TOPIC = "mavlink/in"
# ArduPilot beats at 1 Hz
HEARTBEAT_TIMEOUT = 3.0


def parse(text: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    try:
        content = json.loads(text)
    except ValueError:
        return None

    if not isinstance(content, dict):
        return None
    header, message = content.get("header"), content.get("message")
    if not isinstance(header, dict) or not isinstance(message, dict):
        return None
    return header, message


def autopilot_message(text: str, system_id: int) -> Optional[Dict[str, Any]]:
    parsed = parse(text)
    if parsed is None:
        return None
    header, message = parsed

    if (header.get("system_id"), header.get("component_id")) != (system_id, AUTOPILOT_COMPONENT_ID):
        return None

    if message.get("type") not in AUTOPILOT_MESSAGES:
        return None

    return message


# The autopilot's system id and heartbeat, when the heartbeat is from a vehicle and not a GCS or another component
def vehicle_heartbeat(text: str) -> Optional[Tuple[int, Dict[str, Any]]]:
    parsed = parse(text)
    if parsed is None:
        return None
    header, message = parsed

    mavtype = message.get("mavtype")
    vehicle_type = MavlinkVehicleType.__members__.get(mavtype.get("type", "")) if isinstance(mavtype, dict) else None
    if message.get("type") != "HEARTBEAT" or vehicle_type is None or not vehicle_type.is_actually_a_vehicle():
        return None

    system_id = header.get("system_id")
    return (system_id, message) if isinstance(system_id, int) else None


# mavlink-server writes base_mode as bitflags' names joined by " | ", not mavlink2rest's {"bits": 128}
def armed(heartbeat: Dict[str, Any]) -> bool:
    base_mode = heartbeat.get("base_mode")
    if not isinstance(base_mode, str):
        raise ValueError(f"unexpected HEARTBEAT base_mode from the autopilot: {base_mode!r}")
    return "MAV_MODE_FLAG_SAFETY_ARMED" in (flag.strip() for flag in base_mode.split("|"))


def session() -> zenoh.Session:
    return open_session(SERVICE_NAME)


async def next_heartbeat() -> Tuple[int, Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    heard: "asyncio.Future[Tuple[int, Dict[str, Any]]]" = loop.create_future()

    def settle(beat: Tuple[int, Dict[str, Any]]) -> None:
        if not heard.done():
            heard.set_result(beat)

    # Runs on zenoh's thread
    def on_sample(sample: zenoh.Sample) -> None:
        beat = vehicle_heartbeat(sample.payload.to_string())
        if beat is not None:
            loop.call_soon_threadsafe(settle, beat)

    subscriber = session().declare_subscriber(f"mavlink/*/{AUTOPILOT_COMPONENT_ID}/HEARTBEAT", on_sample)
    try:
        async with asyncio.timeout(HEARTBEAT_TIMEOUT):
            return await heard
    except TimeoutError as error:
        raise ConnectionError(f"no heartbeat from the autopilot in {HEARTBEAT_TIMEOUT:g} s") from error
    finally:
        subscriber.undeclare()  # type: ignore[no-untyped-call]


async def is_armed() -> bool:
    _, heartbeat = await next_heartbeat()
    return armed(heartbeat)


@asynccontextmanager
async def autopilot_link(deliver: Callable[[Any], None]) -> AsyncIterator[Io]:
    loop = asyncio.get_running_loop()
    vehicle = VehicleManager()
    vehicle.set_target_component(AUTOPILOT_COMPONENT_ID)
    # Our header is commonwealth's MavlinkMessenger's, (MAV_SYSTEM_ID, 194); it must differ from the autopilot's
    header = {"system_id": vehicle.mavlink2rest.system_id, "component_id": vehicle.mavlink2rest.component_id}
    # Declared by run() on Connect, so the cleanup below runs for every job that connected
    subscribers: List[zenoh.Subscriber[None]] = []

    async def run(request: Any) -> Any:
        if not isinstance(request, (Connect, Send)):
            raise ValueError(f"the autopilot link only runs Connect and Send, not {request}")

        if isinstance(request, Send):
            message = vehicle.command_long_message(request.command.command, request.command.params)
            session().put(
                SEND_TOPIC,
                json.dumps({"header": {**header, "sequence": 0}, "message": message}),
                encoding=zenoh.Encoding.APPLICATION_JSON,
                congestion_control=zenoh.CongestionControl.BLOCK,
            )
            return None

        system_id, _ = await next_heartbeat()
        vehicle.set_target_system(system_id)

        # Runs on zenoh's thread; call_soon_threadsafe keeps the messages in the order they arrive
        def on_sample(sample: zenoh.Sample) -> None:
            message = autopilot_message(sample.payload.to_string(), system_id)
            if message is not None:
                loop.call_soon_threadsafe(deliver, Heard(message))

        for name in AUTOPILOT_MESSAGES:
            topic = f"mavlink/{system_id}/{AUTOPILOT_COMPONENT_ID}/{name}"
            subscribers.append(session().declare_subscriber(topic, on_sample))
        return Connected()

    try:
        yield run
    finally:
        for subscriber in subscribers:
            subscriber.undeclare()  # type: ignore[no-untyped-call]
