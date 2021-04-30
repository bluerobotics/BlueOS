#!/usr/bin/env python3
import argparse
import asyncio
import logging

from pingmanager import PingManager
from pingprober import PingProber
from portwatcher import PortWatcher


async def main() -> None:
    logging.info("Starting Ping Service")
    pingprober = PingProber()
    pingmanager = PingManager()
    portwatcher = PortWatcher(probe_callback=pingprober.probe)
    portwatcher.set_port_post_callback(pingmanager.stop_driver_at_port)

    pingprober.on_ping_found(pingmanager.launch_driver_instance)

    await portwatcher.start_watching()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ping Service for Bluerobotics Companion")
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("--logtofile", help="log output to a file instead")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO

    logging.basicConfig(filename=args.logtofile, level=level)
    asyncio.run(main())
