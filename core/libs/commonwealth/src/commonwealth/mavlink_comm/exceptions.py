"""
Mavlink-comm exception classes.
"""


class MavlinkMessageSendFail(RuntimeError):
    """Mavlink message could no be sent."""


class MavlinkMessageReceiveFail(RuntimeError):
    """Could not retrieve Mavlink message."""


class FetchUpdatedMessageFail(RuntimeError):
    """Unable to get an updated mavlink message."""


class VehicleDisarmFail(RuntimeError):
    """Could not disarm vehicle."""
