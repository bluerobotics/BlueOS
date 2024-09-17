import argparse
from dataclasses import dataclass


@dataclass
class CommandLineArgs:
    """
    Represents command line argument for Autopilot Manager.

    Attributes:
        debug (bool): Enable debug mode
        host (str): Host to server kraken on
        port (int): Port to server kraken on
    """

    sitl: bool
    debug: bool
    host: str
    port: int

    @staticmethod
    def from_args() -> "CommandLineArgs":
        parser = argparse.ArgumentParser(description="AutoPilot Manager service")

        parser.add_argument("-s", "--sitl", action="store_true", help="run SITL instead of connecting any board")
        parser.add_argument("--debug", action="store_true", default=False, help="Enable debug mode")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to server AutoPilot Manager on")
        parser.add_argument("--port", type=int, default=8000, help="Port to server AutoPilot Manager on")

        args = parser.parse_args()
        client_args = CommandLineArgs(sitl=args.sitl, debug=args.debug, host=args.host, port=args.port)

        return client_args
