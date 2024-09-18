#! /usr/bin/env python3
import argparse
import asyncio
import logging
from pathlib import Path

from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger
from uvicorn import Config, Server

from ArduPilotManager import ArduPilotManager
from flight_controller_detector.Detector import Detector as BoardDetector
from settings import SERVICE_NAME

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting ArduPilot Manager.")
autopilot = ArduPilotManager()

from api import application

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")

parser = argparse.ArgumentParser(description="ArduPilot Manager service for Blue Robotics BlueOS")
parser.add_argument("-s", "--sitl", help="run SITL instead of connecting any board", action="store_true")

args = parser.parse_args()

if not is_running_as_root():
    raise RuntimeError("ArduPilot manager needs to run with root privilege.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=application, loop=loop, host="0.0.0.0", port=8000, log_config=None)
    server = Server(config)

    if args.sitl:
        autopilot.set_preferred_board(BoardDetector.detect_sitl())
    try:
        loop.run_until_complete(autopilot.start_ardupilot())
    except Exception as start_error:
        logger.exception(start_error)
    loop.create_task(autopilot.auto_restart_ardupilot())
    loop.create_task(autopilot.start_mavlink_manager_watchdog())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(autopilot.kill_ardupilot())
