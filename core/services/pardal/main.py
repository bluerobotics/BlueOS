#!/usr/bin/env python

import argparse
import os
from functools import cache
import aiohttp
from aiohttp import web

parser = argparse.ArgumentParser(description="Pardal, web service to help with speed and latency tests")
parser.add_argument("-p", "--port", help="Port to run web server", action="store_true", default=9120)

args = parser.parse_args()


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


app = web.Application()
maximum_number_of_bytes = 2 * (2**30)  # 2 GBs
app._client_max_size = maximum_number_of_bytes
app.add_routes([web.get("/ws", websocket_echo)])
app.router.add_get("/get_file", get_file, name="get_file")
app.router.add_post("/post_file", post_file, name="post_file")
web.run_app(app, path="0.0.0.0", port=args.port)
