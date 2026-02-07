"""Entry point for service-manager daemon."""

import argparse
import asyncio
import sys
from pathlib import Path

from service_manager import __version__
from service_manager.config import AgentConfig
from service_manager.daemon import AgentDaemon, PidLock, daemonize


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="service-manager",
        description="Linux service supervisor with cgroups v2 resource control",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to config file",
    )
    parser.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    # Daemonize BEFORE starting asyncio (only on Linux, and only if not foreground)
    if not args.foreground and sys.platform == "linux":
        config = AgentConfig.load_or_default(args.config)
        pid_lock = PidLock(config.pid_file)

        # Check if already running before forking
        if PidLock.is_running(config.pid_file):
            print("Another instance is already running", file=sys.stderr)
            return 1

        daemonize()

        # Acquire lock after daemonizing (we have a new PID now)
        if not pid_lock.acquire():
            return 1

    daemon = AgentDaemon(
        config_path=args.config,
        foreground=args.foreground or sys.platform != "linux",
    )

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
