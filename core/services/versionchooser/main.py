#! /usr/bin/env python3
import asyncio
import logging

from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from loguru import logger
from uvicorn import Config, Server

from args import CommandLineArgs
from api import application

SERVICE_NAME = "version-chooser"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting Version Chooser")


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    logger.info("Starting Version Chooser service.")

    args = CommandLineArgs.from_args()
    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    config = Config(app=application, host=args.host, port=args.port)
    server = Server(config)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
