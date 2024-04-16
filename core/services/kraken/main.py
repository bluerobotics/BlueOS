#! /usr/bin/env python3
import asyncio
import logging

from loguru import logger
from uvicorn import Config, Server

from api import app
from args import CommandLineArgs
from commonwealth.utils.logs import InterceptHandler, init_logger
from config import SERVICE_NAME
from kraken import Kraken


# Set up logging
logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

# Global Kraken control instance

kraken = Kraken()

# Application entry point

if __name__ == "__main__":
    args = CommandLineArgs.from_args()

    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")

    loop = asyncio.new_event_loop()

    config = Config(app=app, loop=loop, host=args.host, port=args.port, log_config=None)
    server = Server(config)

    # Starts kraken polling loop
    loop.create_task(kraken.start())

    # Serves until completion and stops kraken polling loop
    loop.run_until_complete(server.serve())
    loop.run_until_complete(kraken.stop())
