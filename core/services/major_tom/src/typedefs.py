from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


@dataclass
class ExtensionInfo:
    identifier: str
    tag: str


@dataclass
class VersionInfo:
    repository: str
    tag: str
    last_modified: str
    sha: str
    architecture: str


class OnlineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class TelemetryRecord:
    pass


@dataclass
# pylint: disable=too-many-instance-attributes
class AnonymousTelemetryRecord(TelemetryRecord):
    uptime: float
    latency: float
    memory_size: int
    memory_usage: int
    disk_size: int
    disk_usage: int
    extensions: Optional[list[ExtensionInfo]]
    blueos_version: Optional[VersionInfo]
    probe_time: float

    def json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DefaultPayload:
    log_session_uuid: str
    order: int
    timestamp: str
    hardware_id: str
    blueos_id: str
    data: Optional[TelemetryRecord]

    def json(self) -> dict[str, Any]:
        return asdict(self)
