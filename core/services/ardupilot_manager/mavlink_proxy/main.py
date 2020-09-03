#!/bin/env python
import argparse
import time

# To list all available interfaces
from lib import *
from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint

# Process arguments
AVAILABLE_INTERFACES = AbstractRouter.available_interfaces()
assert AVAILABLE_INTERFACES, "No available interface found."

INTERFACES_NAME = [interface.name() for interface in AVAILABLE_INTERFACES]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Abstraction CLI for multiple mavlink routers")

    parser.add_argument(
        "--master",
        dest="master",
        type=Endpoint,
        required=True,
        help="Master endpoint that follow the format: udp/udpout/tcp/serial:ip/device:port/baudrate",
    )

    parser.add_argument(
        "--out",
        dest="output",
        nargs="*",
        type=Endpoint,
        required=True,
        metavar="endpoint",
        help="List of endpoints that will be used to connect or allow connection.",
    )

    parser.add_argument(
        "--tool",
        dest="tool",
        type=str,
        default=INTERFACES_NAME[0],
        choices=INTERFACES_NAME,
        help="Selected the desired tool to use, the default will be the first one available.",
    )

    args = parser.parse_args()

    tool = AbstractRouter.get_interface(args.tool)()
    print(f"Starting {tool.name()} version {tool.version()}.")

    for endpoint in args.output:
        assert tool.add_endpoint(endpoint)

    print(f"Command: {tool.assemble_command(args.master)}")
    tool.start(args.master)

    while tool.is_running():
        time.sleep(1)
    print("Tool finished.")
