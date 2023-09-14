#!/usr/bin/env python

import argparse
import logging
import os
from functools import cache

import aiohttp
from aiohttp import web
from commonwealth.utils.general import limit_ram_usage
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "pardal"

limit_ram_usage()

parser = argparse.ArgumentParser(description="Pardal, web service to help with speed and latency tests")
parser.add_argument("-p", "--port", help="Port to run web server", action="store_true", default=9120)

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting Pardal")


@cache
def generate_random_data(size: int) -> bytes:
    return os.urandom(size)


async def websocket_echo(request: web.Request) -> web.WebSocketResponse:
    websocket = web.WebSocketResponse()
    await websocket.prepare(request)

    async for message in websocket:
        if message.type == aiohttp.WSMsgType.TEXT:
            await websocket.send_str(message.data)

    return websocket


async def get_file(request: web.Request) -> web.Response:
    size = int(request.rel_url.query.get("size", 100 * (2**20)))  # 100MB by default
    return web.Response(status=200, body=generate_random_data(size))


async def post_file(request: web.Request) -> web.Response:
    # pylint: disable=unused-variable
    data = await request.read()
    return web.Response(status=200)


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


app = web.Application()
maximum_number_of_bytes = 2 * (2**30)  # 2 GBs
app._client_max_size = maximum_number_of_bytes
app.add_routes([web.get("/ws", websocket_echo)])
app.router.add_get("/", root, name="root")
app.router.add_get("/get_file", get_file, name="get_file")
app.router.add_post("/post_file", post_file, name="post_file")
web.run_app(app, path="0.0.0.0", port=args.port)
