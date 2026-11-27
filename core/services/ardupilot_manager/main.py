#! /usr/bin/env python3
import asyncio
import logging

from args import CommandLineArgs
from autopilot_manager import AutoPilotManager
from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from config import SERVICE_NAME
from flight_controller_detector.Detector import Detector as BoardDetector
from loguru import logger
from uvicorn import Config, Server

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting AutoPilot Manager.")

# CAP_SYS_ADMIN lets root open serial ports locked with TIOCEXCL. Dropping it makes the in-process serial probing
# skip ports held by the MAVLink router or the firmware uploader instead of stealing their data.
# This only applies to this Python process and the threads it creates afterwards: root children exec'd later
# (router, uploader, ArduPilot) regain it from the bounding set.
try:
    import prctl

    prctl.cap_effective.drop(prctl.CAP_SYS_ADMIN)
    prctl.cap_permitted.drop(prctl.CAP_SYS_ADMIN)
    logger.info("Dropped CAP_SYS_ADMIN from the AutoPilot Manager process")
except ImportError:
    logger.warning("prctl module not available, serial probing may interfere with ports in use")
except Exception as e:
    logger.warning(f"Failed to drop CAP_SYS_ADMIN, serial probing may interfere with ports in use: {e}")

autopilot = AutoPilotManager()

from api import application

if not is_running_as_root():
    raise RuntimeError("AutoPilot manager needs to run with root privilege.")


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    args = CommandLineArgs.from_args()
    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the AutoPilot Manager service.")

    config = Config(app=application, host=args.host, port=args.port, log_config=None)
    server = Server(config)

    if args.sitl:
        autopilot.set_preferred_board(BoardDetector.detect_sitl())

    if autopilot.should_start_on_boot():
        try:
            await autopilot.start_ardupilot()
        except Exception as start_error:
            logger.exception(start_error)
    else:
        logger.info("Autopilot was stopped by the user, skipping auto-start on boot.")

    # Keep references so the event loop can't garbage-collect the watchdogs
    watchdogs = [  # pylint: disable=unused-variable
        asyncio.create_task(autopilot.auto_restart_ardupilot()),
        asyncio.create_task(autopilot.start_mavlink_manager_watchdog()),
    ]

    await server.serve()
    await autopilot.kill_ardupilot()


if __name__ == "__main__":
    asyncio.run(main())
