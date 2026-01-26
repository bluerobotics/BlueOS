#! /usr/bin/env python3
import asyncio
import logging

from args import CommandLineArgs
from autopilot_manager import AutoPilotManager
from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from flight_controller_detector.Detector import Detector as BoardDetector
from loguru import logger
from settings import SERVICE_NAME
from uvicorn import Config, Server

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting AutoPilot Manager.")

# Drop CAP_SYS_ADMIN capability for the entire service as it's not needed
# Serial port access, process management, and file operations don't require it
try:
    import prctl

    prctl.cap_effective.drop(prctl.CAP_SYS_ADMIN)
    prctl.cap_permitted.drop(prctl.CAP_SYS_ADMIN)
    logger.info("Dropped CAP_SYS_ADMIN capability for security")
except ImportError:
    logger.warning("prctl module not available - cannot drop capabilities")
except Exception as e:
    logger.warning(f"Failed to drop CAP_SYS_ADMIN capability: {e}")

autopilot = AutoPilotManager()

from api import application

if not is_running_as_root():
    logger.error("AutoPilot manager needs to run with root privilege.")
    logger.error("expect issues")


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
    try:
        await autopilot.start_ardupilot()
    except Exception as start_error:
        logger.exception(start_error)

    asyncio.create_task(autopilot.auto_restart_ardupilot())
    asyncio.create_task(autopilot.start_mavlink_manager_watchdog())

    await server.serve()
    await autopilot.kill_ardupilot()


if __name__ == "__main__":
    asyncio.run(main())
