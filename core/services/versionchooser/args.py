import argparse
from dataclasses import dataclass


@dataclass
class CommandLineArgs:
    """
    Represents command-line arguments for Version Chooser.

    Attributes:
        debug (bool): Enable debug mode
        host (str): Host to server version-chooser on
        port (int): Port to server version-chooser on
    """

    debug: bool
    host: str
    port: int

    @staticmethod
    def from_args() -> "CommandLineArgs":
        parser = argparse.ArgumentParser(description="Version Chooser Manager service.")

        parser.add_argument("--debug", action="store_true", default=False, help="Enable debug mode")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to server version-chooser on")
        parser.add_argument("--port", type=int, default=8081, help="Port to server version-chooser on")

        args = parser.parse_args()
        client_args = CommandLineArgs(debug=args.debug, host=args.host, port=args.port)

        return client_args
