""" Request distance measurements from a Blue Robotics Ping1D device over UDP (PingProxy).
    Send results to an autopilot via MAVLink over UDP, for use as a rangefinder.
    Don't request if we are already getting data from device (e.g. there is another client
    (pingviewer gui) making requests to the proxy).
"""

import asyncio
import socket
import time
from select import select
from typing import Any, Dict

from brping import (
    PING1D_DISTANCE,
    PING1D_DISTANCE_SIMPLE,
    PING1D_PROFILE,
    PING1D_SET_PING_INTERVAL,
    PingMessage,
    PingParser,
)
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from loguru import logger

## The minimum interval time for distance updates to the autopilot
PING_INTERVAL_S = 0.1


class Ping1DMavlinkDriver:
    mavlink2rest = MavlinkMessenger()

    def __init__(self, should_run: bool) -> None:
        self.should_run = should_run
        self.time_since_boot = time.time()
        self.ping1d_io = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ping1d_io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ping1d_io.setblocking(False)
        ## Parser to decode incoming PingMessage
        self.parser = PingParser()

    def set_should_run(self, should_run: bool) -> None:
        self.should_run = should_run

    @staticmethod
    def distance_message(time_boot_ms: int, distance_cm: int, device_id: int, confidence: int) -> Dict[str, Any]:
        return {
            "type": "DISTANCE_SENSOR",
            "time_boot_ms": time_boot_ms,
            "min_distance": 20,
            "max_distance": 12000,
            "current_distance": int(distance_cm),
            "mavtype": {"type": "MAV_DISTANCE_SENSOR_ULTRASOUND"},
            "id": device_id,
            "orientation": {"type": "MAV_SENSOR_ROTATION_PITCH_270"},
            "covariance": 255,
            "horizontal_fov": 0.52,
            "vertical_fov": 0.52,
            "quaternion": [0, 0, 0, 0],
            "signal_quality": max(1, confidence),  # 0 means undefined per MAVLink spec
        }

    ## Send distance_sensor message to autopilot
    async def send_distance_data(self, distance: int, deviceid: int, confidence: int) -> None:
        logger.info(f"sending {distance} ({confidence})")
        await self.mavlink2rest.send_mavlink_message(
            self.distance_message(
                int((time.time() - self.time_since_boot) * 1000), int(distance / 10), deviceid, confidence
            )
        )

    ## Send a request for distance_simple message to ping device
    async def send_ping1d_request(
        self,
    ) -> None:
        logger.debug("requesting new data")
        data = PingMessage()
        data.request_id = PING1D_DISTANCE_SIMPLE
        data.src_device_id = 0
        data.pack_msg_data()
        self.ping1d_io.sendall(data.msg_data)

    def create_interval_message(self) -> PingMessage:
        interval_message = PingMessage()
        interval_message.request_id = PING1D_SET_PING_INTERVAL
        interval_message.src_device_id = 0
        interval_message.ping_interval = int(PING_INTERVAL_S * 1000)
        interval_message.pack_msg_data()
        return interval_message

    async def drive(self, port: int) -> None:

        ## Messages that have the current distance measurement in the payload
        distance_messages = [PING1D_DISTANCE, PING1D_DISTANCE_SIMPLE, PING1D_PROFILE]

        last_distance_measurement_time = 0.0

        last_ping_request_time = 0.0

        pingserver = ("127.0.0.1", port)
        self.ping1d_io.connect(pingserver)

        # set the ping interval once at startup
        # the ping interval may change if another client to the pingproxy requests it
        interval_message = self.create_interval_message()
        self.ping1d_io.sendall(interval_message.msg_data)

        while True:
            if not self.should_run:
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(0.1 * PING_INTERVAL_S)
            now = time.perf_counter()

            # request data from ping device
            if now > last_distance_measurement_time + PING_INTERVAL_S * 2.5:
                if now > last_ping_request_time + PING_INTERVAL_S:
                    last_ping_request_time = time.perf_counter()
                    await self.send_ping1d_request()

                # deal with possibly lost connection
                if now > last_distance_measurement_time + PING_INTERVAL_S * 10:
                    logger.info("attempting reconnection...")
                    self.ping1d_io.connect(pingserver)
                    last_distance_measurement_time = time.perf_counter()

            # read data in from ping device
            data = b""
            while select([self.ping1d_io], [], [], 0)[0]:
                data += self.ping1d_io.recv(4096)

            if not data or now - last_distance_measurement_time < PING_INTERVAL_S * 0.5:
                # skip decoding data to save cpu if it is arriving too fast
                self.parser.state = self.parser.WAIT_START
                continue
            # decode data from ping device, forward to autopilot
            new_data_available = False
            distance = 0
            deviceid = 0
            confidence = 0

            for byte in data:
                try:
                    if (
                        self.parser.parse_byte(byte) == PingParser.NEW_MESSAGE
                        and self.parser.rx_msg.message_id in distance_messages
                    ):
                        last_distance_measurement_time = time.perf_counter()
                        new_data_available = True
                        distance = self.parser.rx_msg.distance
                        deviceid = self.parser.rx_msg.src_device_id
                        confidence = self.parser.rx_msg.confidence
                except Exception as error:
                    logger.warning(error)
            if new_data_available:
                try:
                    await self.send_distance_data(distance, deviceid, confidence)
                except Exception as error:
                    logger.warning(error)
