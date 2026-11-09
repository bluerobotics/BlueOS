import asyncio
import logging

from api.app import app
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from config import PORT, SERVICE_NAME
from loguru import logger
from uvicorn import Config, Server

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Vehicle Setup Service.")


async def main() -> None:
    try:
        await init_sentry_async(SERVICE_NAME)

        config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
        server = Server(config)

        await server.serve()
    finally:
        logger.info("Vehicle Setup service stopped")


if __name__ == "__main__":
    asyncio.run(main())
