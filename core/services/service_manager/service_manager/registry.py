"""Service registry - in-memory service state management."""
# pylint: disable=too-many-instance-attributes,too-many-arguments

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from service_manager.config import ServiceSpec


class ServiceStatus(str, Enum):
    """Service status states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServiceState:
    """Runtime state of a service."""

    spec: ServiceSpec
    status: ServiceStatus = ServiceStatus.STOPPED
    pid: int | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    restart_count: int = 0
    _process: asyncio.subprocess.Process | None = field(default=None, repr=False)

    @property
    def is_running(self) -> bool:
        return self.status in (ServiceStatus.RUNNING, ServiceStatus.STARTING)

    @property
    def uptime_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        if self.status == ServiceStatus.RUNNING:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds()
        if self.stopped_at:
            return (self.stopped_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        limits = self.spec.limits
        return {
            "name": self.spec.name,
            "status": self.status.value,
            "pid": self.pid,
            "exit_code": self.exit_code,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "restart_count": self.restart_count,
            "uptime_seconds": self.uptime_seconds,
            "command": self.spec.command,
            "enabled": self.spec.enabled,
            "restart": self.spec.restart,
            "env": self.spec.env,
            "cwd": str(self.spec.cwd) if self.spec.cwd else None,
            "restart_delay_sec": self.spec.restart_delay_sec,
            "stop_timeout_sec": self.spec.stop_timeout_sec,
            "limits": {
                "cpu_cores": limits.cpu_cores,
                "memory_mb": limits.memory_mb,
                "io_read_mbps": limits.io_read_mbps,
                "io_write_mbps": limits.io_write_mbps,
                "max_pids": limits.max_pids,
            },
        }


class ServiceRegistry:
    """In-memory registry of all services."""

    def __init__(self) -> None:
        self._services: dict[str, ServiceState] = {}
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[str, ServiceStatus], None]] = []

    def register(self, spec: ServiceSpec) -> ServiceState:
        """Register a new service from spec."""
        state = ServiceState(spec=spec)
        self._services[spec.name] = state
        return state

    def get(self, name: str) -> ServiceState | None:
        """Get service state by name."""
        return self._services.get(name)

    def all(self) -> list[ServiceState]:
        """Get all service states."""
        return list(self._services.values())

    def remove(self, name: str) -> bool:
        """Remove a service from registry."""
        if name in self._services:
            del self._services[name]
            return True
        return False

    def update_spec(self, spec: ServiceSpec) -> None:
        """Update the spec for an existing service."""
        state = self._services.get(spec.name)
        if state:
            state.spec = spec

    async def update_status(
        self,
        name: str,
        status: ServiceStatus,
        pid: int | None = None,
        exit_code: int | None = None,
        process: asyncio.subprocess.Process | None = None,
    ) -> None:
        """Update service status with optional metadata."""
        async with self._lock:
            state = self._services.get(name)
            if state is None:
                return

            old_status = state.status
            state.status = status

            if pid is not None:
                state.pid = pid

            if exit_code is not None:
                state.exit_code = exit_code

            if process is not None:
                state._process = process

            now = datetime.now(timezone.utc)

            if status == ServiceStatus.RUNNING and old_status != ServiceStatus.RUNNING:
                state.started_at = now
                state.stopped_at = None
                state.exit_code = None

            if status in (ServiceStatus.STOPPED, ServiceStatus.FAILED):
                state.stopped_at = now
                state._process = None

            # Notify listeners
            for listener in self._listeners:
                try:
                    listener(name, status)
                except Exception:
                    pass

    def get_process(self, name: str) -> asyncio.subprocess.Process | None:
        """Get the subprocess object for a running service."""
        state = self._services.get(name)
        if state:
            return state._process
        return None

    def increment_restart_count(self, name: str) -> None:
        """Increment restart counter for a service."""
        state = self._services.get(name)
        if state:
            state.restart_count += 1

    def reset_restart_count(self, name: str) -> None:
        """Reset restart counter for a service."""
        state = self._services.get(name)
        if state:
            state.restart_count = 0

    def add_listener(self, callback: Callable[[str, ServiceStatus], None]) -> None:
        """Add a status change listener."""
        self._listeners.append(callback)

    def running_services(self) -> list[ServiceState]:
        """Get all running services."""
        return [s for s in self._services.values() if s.is_running]

    def names(self) -> list[str]:
        """Get all service names."""
        return list(self._services.keys())
