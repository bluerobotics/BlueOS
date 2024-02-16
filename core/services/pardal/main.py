#!/usr/bin/env python

import argparse
import logging
import os
from typing import Generator

import aiohttp
from aiohttp import web
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "pardal"

parser = argparse.ArgumentParser(description="Pardal, web service to help with speed and latency tests")
parser.add_argument("-p", "--port", help="Port to run web server", action="store_true", default=9120)

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting Pardal")


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
