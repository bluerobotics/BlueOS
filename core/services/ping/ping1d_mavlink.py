#!/usr/bin/python -u

""" Request distance measurements from a Blue Robotics Ping1D device over udp (PingProxy)
    Send results to autopilot via mavproxy over udp for use as mavlink rangefinder
    Don't request if we are already getting data from device (ex. there is another client
    (pingviewer gui) making requests to the proxy)
"""

import asyncio
import errno
import socket
import time
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


class Ping1DMavlinkDriver:
    mavlink2rest = MavlinkMessenger()

    def __init__(self, should_run):
        self.should_run = should_run

    def set_should_run(self, should_run):
        self.should_run = should_run

    def distance_message(self, time_boot_ms: int, distance: int, device_id: int) -> Dict[str, Any]:
        return {
            "type": "DISTANCE_SENSOR",
            "time_boot_ms": time_boot_ms,
            "min_distance": 20,
            "max_distance": 5000,
            "current_distance": int(distance),
            "mavtype": {"type": "MAV_DISTANCE_SENSOR_LASER"},
            "id": device_id,
            "orientation": {"type": "MAV_SENSOR_ROTATION_PITCH_270"},
            "covariance": 0,
            "horizontal_fov": 0,
            "vertical_fov": 0,
            "quaternion": [0, 0, 0, 0],
            "signal_quality": 0,
        }

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    async def drive(self, port: int) -> None:
        """Main function"""
        ## The time that this script was started
        tboot = time.time()

        ## Parser to decode incoming PingMessage
        ping_parser = PingParser()

        ## Messages that have the current distance measurement in the payload
        distance_messages = [PING1D_DISTANCE, PING1D_DISTANCE_SIMPLE, PING1D_PROFILE]

        ## The minimum interval time for distance updates to the autopilot
        ping_interval_ms = 0.2

        ## The last time a distance measurement was received
        last_distance_measurement_time = 0.0

        ## The last time a distance measurement was requested
        last_ping_request_time = 0.0

        pingserver = ("127.0.0.1", port)

        ## Send distance_sensor message to autopilot
        async def send_distance_data(distance: int, deviceid: int, confidence: int) -> None:
            # logger.debug("sending distance %d confidence %d" % (distance, confidence))
            if confidence < 0.5:
                distance = 0
            logger.debug(f"sendind {distance}")
            await self.mavlink2rest.send_mavlink_message(
                self.distance_message(int((time.time() - tboot) * 1000), int(distance / 10), deviceid)
            )

        ## Send a request for distance_simple message to ping device
        async def send_ping1d_request() -> None:
            logger.debug("requesting new data")
            data = PingMessage()
            data.request_id = PING1D_DISTANCE_SIMPLE
            data.src_device_id = 0
            data.pack_msg_data()
            ping1d_io.sendall(data.msg_data)

        ping1d_io = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ping1d_io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ping1d_io.setblocking(False)
        ping1d_io.connect(pingserver)

        # set the ping interval once at startup
        # the ping interval may change if another client to the pingproxy requests it
        data = PingMessage()
        data.request_id = PING1D_SET_PING_INTERVAL
        data.src_device_id = 0
        data.ping_interval = int(ping_interval_ms * 1000)
        data.pack_msg_data()
        ping1d_io.sendall(data.msg_data)

        while True:
            if not self.should_run:
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(0.001)
            tnow = time.time()

            # request data from ping device
            if tnow > last_distance_measurement_time + ping_interval_ms:
                if tnow > last_ping_request_time + ping_interval_ms:
                    last_ping_request_time = time.time()
                    await send_ping1d_request()

            if tnow > last_distance_measurement_time + ping_interval_ms * 10:
                logger.info("attempting reconnection...")
                ping1d_io.connect(pingserver)
                await asyncio.sleep(0.1)

            # read data in from ping device
            try:
                data, _ = ping1d_io.recvfrom(4096)
            except socket.error as exception:
                # check if it's waiting for data
                if exception.errno == errno.EAGAIN:
                    continue
                elif exception.errno == errno.ECONNREFUSED:
                    logger.warning("Ping1D connection lost, stopping MAVLink driver")
                    return
                continue

            if tnow - last_distance_measurement_time < ping_interval_ms * 0.8:
                # skip decoding data if too fast
                continue
            # decode data from ping device, forward to autopilot
            for byte in data:
                try:
                    if ping_parser.parse_byte(byte) == PingParser.NEW_MESSAGE:
                        if ping_parser.rx_msg.message_id in distance_messages:
                            last_distance_measurement_time = time.time()
                            distance = ping_parser.rx_msg.distance
                            deviceid = ping_parser.rx_msg.src_device_id
                            confidence = ping_parser.rx_msg.confidence
                            await send_distance_data(distance, deviceid, confidence)
                except Exception as error:
                    logger.warning(error)
