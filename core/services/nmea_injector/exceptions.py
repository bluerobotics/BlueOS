"""
NMEA Injector exception classes.
"""


class UnsupportedSentenceType(ValueError):
    """NMEA sentence type not supported."""


class UnsupportedSocketKind(ValueError):
    """Socket type provided is not supported."""


class ReceiveFailure(ValueError):
    """Failed to receive external data."""
