"""
Wifi-manager exception classes.
"""


class ParseError(ValueError):
    """Raise for errors regarding fail parsing string data to proper structs."""


class FetchError(ValueError):
    """Raise for errors regarding fail on fetching data."""


class BusyError(ValueError):
    """Raise for errors regarding excessive number of requests on a given time."""
