#! /usr/bin/env python3
import asyncio
import logging

from api import application
from args import CommandLineArgs
from commonwealth.utils.events import events
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from loguru import logger
from uvicorn import Config, Server

SERVICE_NAME = "version-chooser"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)
events.publish_start()

logger.info("Starting Version Chooser")


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    logger.info("Starting Version Chooser service.")

    args = CommandLineArgs.from_args()
    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    config = Config(app=application, host=args.host, port=args.port)
    server = Server(config)

    # Publish running event when service is ready
    events.publish_running()
    events.publish_health("ready", {"endpoint": f"{args.host}:{args.port}"})

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
