#!/bin/env python
import argparse
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
        type=str,
        default=interfaces[0].name(),
        choices=[interface.name() for interface in interfaces],
        help="Selected the desired tool to use, the default will be the first one available.",
    )

    args = parser.parse_args()

    tool = AbstractRouter.get_interface(args.tool)()
    logger.info(f"Starting {tool.name()} version {tool.version()}.")

    manager.use(tool)
    manager.add_endpoints(args.output.split(":"))

    logger.info(f"Command: {manager.command_line()}")
    manager.start(args.master.split(":"))
    while manager.is_running():
        time.sleep(1)
    logger.info("Done.")
