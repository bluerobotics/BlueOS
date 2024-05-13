import argparse

from dataclasses import dataclass


@dataclass
class CommandLineArgs:
    """
    Represents command-line arguments for the client.

    Attributes:
        debug (bool): Enable debug mode
        host (str): Host to server kraken on
        port (int): Port to server kraken on
    """

    debug: bool
    host: str
    port: int

    @staticmethod
    def from_args() -> "CommandLineArgs":
        parser = argparse.ArgumentParser(
            description = "Kraken Extension manager client."
        )

        # Define command-line arguments
        parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help="Enable debug mode"
        )
        parser.add_argument(
            "--host",
            type=str,
            default="0.0.0.0",
            help="Host to server kraken on"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=9134,
            help="Port to server kraken on"
        )

        # Fetch raw args
        args = parser.parse_args()

        # Creates client command line instance
        client_args = CommandLineArgs(
            debug=args.debug,
            host=args.host,
            port=args.port
        )

        return client_args
