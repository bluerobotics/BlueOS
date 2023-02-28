#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
from typing import Any, List

from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

from major_tom import MajorTom

SERVICE_NAME = "major_tom"
logging.basicConfig(handlers=[InterceptHandler()], level=0)


class BlacklistSpec(BaseModel):
    """Basic black list for things users don't want to send in the telemetry."""

    blacklist: List[str]


try:
    init_logger(SERVICE_NAME)
except Exception as e:
    print(f"unable to set logging path: {e}")

app = FastAPI(
    title="Major Tom API",
    description="Major Tom is responsible for fetching telemetry information and sending it back to Ground Control.",
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Major Tom to Ground Control, commencing countdown, engines on.")

app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

majorTom = MajorTom()


@app.get("/")
async def root() -> Any:
    html_content = """
    <html>
        <head>
            <title>Major Tom</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/blacklist")
@version(1, 0)
async def get_blacklist() -> Any:
    html_content = json.dumps(majorTom.get_blacklist())
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/blacklist")
@version(1, 0)
async def set_blacklist(blacklist: BlacklistSpec) -> Any:
    MajorTom().set_blacklist(blacklist.blacklist)
    return HTMLResponse(content="ok", status_code=200)


@app.get("/remote")
@version(1, 0)
async def get_remote() -> Any:
    return HTMLResponse(content=majorTom.get_remote(), status_code=200)


@app.post("/remote")
@version(1, 0)
async def set_remote(remote: str) -> Any:
    MajorTom().set_remote(remote)
    return HTMLResponse(content="ok", status_code=200)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logger.info("Releasing the Major Tom service.")

    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=9456, log_config=None)
    server = Server(config)

    loop.create_task(majorTom.run())
    loop.run_until_complete(server.serve())
