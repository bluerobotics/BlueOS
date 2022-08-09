class InvalidDeviceDescriptor(RuntimeError):
    """PingDeviceDescripttor is invalid."""


class NoUDPPortAssignedToPingDriver(RuntimeError):
    """PingDriver attempted to start with no UDP port assigned."""
