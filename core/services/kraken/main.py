#! /usr/bin/env python3
import asyncio
import logging

from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger
from uvicorn import Config, Server

from api import application
from args import CommandLineArgs
from config import SERVICE_NAME

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

from kraken import kraken_instance

if __name__ == "__main__":
    args = CommandLineArgs.from_args()

    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")

    loop = asyncio.new_event_loop()

    config = Config(app=application, loop=loop, host=args.host, port=args.port, log_config=None)
    server = Server(config)

    loop.create_task(kraken_instance.run())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(kraken_instance.stop())
