#!/usr/bin/env python

import argparse
import asyncio
import logging
import os
from typing import Generator, Optional

import aiohttp
from aiohttp import web
from commonwealth.utils.events import events
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from loguru import logger
from speedtest import Speedtest

SERVICE_NAME = "pardal"
SPEED_TEST: Optional[Speedtest] = None

parser = argparse.ArgumentParser(description="Pardal, web service to help with speed and latency tests")
parser.add_argument("-p", "--port", help="Port to run web server", action="store_true", default=9120)

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)
events.publish_start()

logger.info("Starting Pardal")

routes = web.RouteTableDef()

try:
    SPEED_TEST = Speedtest(secure=True)
except Exception:
    # When starting, the system may not be connected to the internet
    pass


def generate_random_data(size: int, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
    remaining_size = size
    while remaining_size > 0:
        yield os.urandom(min(chunk_size, remaining_size))
        remaining_size -= chunk_size


async def websocket_echo(request: web.Request) -> web.WebSocketResponse:
    websocket = web.WebSocketResponse()
    await websocket.prepare(request)

    async for message in websocket:
        if message.type == aiohttp.WSMsgType.TEXT:
            await websocket.send_str(message.data)

    return websocket


async def get_file(request: web.Request) -> web.StreamResponse:
    size = int(request.rel_url.query.get("size", 100 * (2**20)))  # 100MB by default

    response = web.StreamResponse(status=200)
    response.headers["Content-Length"] = str(size)
    await response.prepare(request)

    for data_chunk in generate_random_data(size):
        await response.write(bytes(data_chunk))

    await response.write_eof()
    return response


async def post_file(request: web.Request) -> web.Response:
    while True:
        chunk = await request.content.readany()
        if not chunk:
            break
    return web.Response(status=200)


@routes.get("/internet_best_server")
async def internet_best_server(request: web.Request) -> web.Response:
    """
    Check internet best server for test from BlueOS.
    """
    # Since we are finding a new server, clear previous results
    # pylint: disable=global-statement

    interface_addr = request.query.get("interface_addr") or None

    global SPEED_TEST
    SPEED_TEST = Speedtest(secure=True, source_address=interface_addr)
    SPEED_TEST.get_best_server()
    return web.json_response(SPEED_TEST.results.dict())


# pylint: disable=unused-argument
@routes.get("/internet_download_speed")
async def internet_download_speed(request: web.Request) -> web.Response:
    """
    Check internet download speed test from BlueOS.
    """
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    SPEED_TEST.download()
    return web.json_response(SPEED_TEST.results.dict())


# pylint: disable=unused-argument
@routes.get("/internet_upload_speed")
async def internet_upload_speed(request: web.Request) -> web.Response:
    """
    Check internet upload speed test from BlueOS.
    """
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    SPEED_TEST.upload(pre_allocate=False)
    return web.json_response(SPEED_TEST.results.dict())


# pylint: disable=unused-argument
@routes.get("/internet_test_previous_result")
async def internet_test_previous_result(request: web.Request) -> web.Response:
    """
    Return previous result of internet speed test.
    """
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    return web.json_response(SPEED_TEST.results.dict())


# pylint: disable=unused-argument
async def root(request: web.Request) -> web.Response:
    html_content = """
    <html>
        <head>
            <title>Pardal</title>
        </head>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    app = web.Application()
    app.client_max_size = 2 * (2**30)  # 2 GBs

    app.add_routes([web.get("/ws", websocket_echo), *routes])
    app.router.add_get("/", root, name="root")
    app.router.add_get("/get_file", get_file, name="get_file")
    app.router.add_post("/post_file", post_file, name="post_file")

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=args.port)
    await site.start()

    # Publish running event when service is ready
    events.publish_running()
    events.publish_health("ready", {"port": args.port})

    # Wait forever
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
