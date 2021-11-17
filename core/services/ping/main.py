#!/usr/bin/env python3
import argparse
import asyncio
import logging

from pingmanager import PingManager
from pingprober import PingProber
from portwatcher import PortWatcher


async def main() -> None:
    logging.info("Starting Ping Service")
    ping_prober = PingProber()
    ping_manager = PingManager()
    port_watcher = PortWatcher(probe_callback=ping_prober.probe)
    port_watcher.set_port_post_callback(ping_manager.stop_driver_at_port)

    ping_prober.on_ping_found(ping_manager.launch_driver_instance)

    await port_watcher.start_watching()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ping Service for Bluerobotics Companion")
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("--logtofile", help="log output to a file instead")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO

    logging.basicConfig(filename=args.logtofile, level=level)
    asyncio.run(main())
