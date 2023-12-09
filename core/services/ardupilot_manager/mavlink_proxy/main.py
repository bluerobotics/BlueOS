#!/bin/env python
import argparse
import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

# Import local library
sys.path.append(str(Path(__file__).absolute().parent.parent))

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Manager import Manager

if __name__ == "__main__":
    manager = Manager()
    interfaces = manager.available_interfaces()
    parser = argparse.ArgumentParser(description="Abstraction CLI for multiple mavlink routers")

    parser.add_argument(
        "--master",
        dest="master",
        type=str,
        required=True,
        help="Master endpoint that follow the format: udp/udpout/tcp/serial:ip/device:port/baudrate",
    )

    parser.add_argument(
        "--out",
        dest="output",
        nargs="*",
        type=str,
        required=True,
        metavar="endpoint",
        help="List of endpoints that will be used to connect or allow connection.",
    )

    parser.add_argument(
        "--tool",
        dest="tool",
        choices=[interface.name() for interface in interfaces],
        help="Select the desired tool to use, this will override the one in the settings file."
        + " The default will be the first one available.",
    )

    args = parser.parse_args()

    async def main() -> None:
        tool = AbstractRouter.get_interface(args.tool)()

        if tool:
            manager.use(tool)
        else:
            logger.warning(f"No tool selected. Falling back to {interfaces[0]}")
            manager.use(interfaces[0]())

        logger.info(f"Starting {tool.name()} version {tool.version()}.")

        manager.add_endpoints(args.output.split(":"))

        logger.info(f"Command: {manager.command_line()}")
        await manager.start(args.master.split(":"))
        while manager.is_running():
            time.sleep(1)
        logger.info("Done.")

    asyncio.run(main())
