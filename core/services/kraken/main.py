#! /usr/bin/env python3
import asyncio
import logging

from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger
from uvicorn import Config, Server

from args import CommandLineArgs
from config import SERVICE_NAME

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

from api import application
from jobs import JobsManager
from kraken import Kraken

kraken = Kraken()
jobs = JobsManager()

if __name__ == "__main__":
    args = CommandLineArgs.from_args()

    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")
    loop = asyncio.new_event_loop()

    config = Config(app=application, loop=loop, host=args.host, port=args.port, log_config=None)
    server = Server(config)
    jobs.set_base_host(f"http://{args.host}:{args.port}")

    loop.create_task(kraken.start())
    loop.create_task(jobs.start())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(jobs.stop())
    loop.run_until_complete(kraken.stop())
