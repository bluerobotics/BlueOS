#! /usr/bin/env python3
import asyncio
import logging

from args import CommandLineArgs
from commonwealth.utils.events import events
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from config import SERVICE_NAME
from loguru import logger
from uvicorn import Config, Server

from args import CommandLineArgs
from config import SERVICE_NAME

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)
events.publish_start()

from api import application
from jobs import JobsManager
from kraken import Kraken

kraken = Kraken()
jobs = JobsManager()


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    args = CommandLineArgs.from_args()

    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")

    config = Config(app=application, host=args.host, port=args.port, log_config=None)
    server = Server(config)

    jobs.set_base_host(f"http://{args.host}:{args.port}")

    # Publish running event when service is ready
    events.publish_running()
    events.publish_health("ready", {"endpoint": f"{args.host}:{args.port}"})

    # Launch background tasks
    asyncio.create_task(kraken.start_cleaner_task())
    asyncio.create_task(kraken.start_starter_task())
    asyncio.create_task(kraken.start_extension_logs_task())
    asyncio.create_task(jobs.start())

    await server.serve()

    await jobs.stop()
    await kraken.stop()


if __name__ == "__main__":
    asyncio.run(main())
