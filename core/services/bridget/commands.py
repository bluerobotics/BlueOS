from dataclasses import dataclass


@dataclass(frozen=True)
class AddBridge:
    """Command: create a live bridge and persist it."""

    serial_path: str
    baud: int
    ip: str
    udp_target_port: int
    udp_listen_port: int


@dataclass(frozen=True)
class RemoveBridge:
    """Command: stop a live bridge and drop it from settings."""

    serial_path: str
    baud: int
    ip: str
    udp_target_port: int
    udp_listen_port: int
