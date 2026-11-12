"""
Wifi-manager exception classes.
"""


class ParseError(ValueError):
    """Raise for errors regarding fail parsing string data to proper structs."""


class FetchError(ValueError):
    """Raise for errors regarding fail on fetching data."""


class BusyError(ValueError):
    """Raise for errors regarding excessive number of requests on a given time."""


class SockCommError(ConnectionError):
    """Raise for errors regarding WPA socket communication."""


class WPAOperationFail(ConnectionError):
    """Raised when a WPA operation fails."""


class NetworkAddFail(ValueError):
    """Raised when a WPA add_network operation fails to return an int."""


class InterfaceNotFound(ValueError):
    """Raised when a requested wifi interface does not exist."""

    def __init__(self, interface: str) -> None:
        super().__init__(f"Wifi interface '{interface}' not found.")
