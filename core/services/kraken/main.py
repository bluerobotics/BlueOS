#! /usr/bin/env python3
import asyncio
from api import app
from uvicorn import Config, Server
from args import CommandLineArgs

if __name__ == "__main__":
    args = CommandLineArgs.from_args()

    loop = asyncio.new_event_loop()

    config = Config(app=app, loop=loop, host=args.host, port=args.port, log_config=None)
    server = Server(config)

    loop.run_until_complete(server.serve())
