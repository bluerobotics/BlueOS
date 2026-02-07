"""Configuration parsing and dataclasses."""
# pylint: disable=import-outside-toplevel,too-many-instance-attributes

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class ResourceLimits:
    """Resource limits for a service (cgroups v2)."""

    cpu_cores: float | None = None  # e.g., 1.5 = 150% of one core
    memory_mb: int | None = None  # hard limit in MB
    io_read_mbps: int | None = None  # MB/sec
    io_write_mbps: int | None = None  # MB/sec
    max_pids: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceLimits:
        return cls(
            cpu_cores=data.get("cpu_cores"),
            memory_mb=data.get("memory_mb"),
            io_read_mbps=data.get("io_read_mbps"),
            io_write_mbps=data.get("io_write_mbps"),
            max_pids=data.get("max_pids"),
        )


@dataclass
class ServiceSpec:
    """Specification for a managed service."""

    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: Path | None = None
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    enabled: bool = True  # start on agent startup
    restart: bool = False  # auto-restart on exit
    restart_delay_sec: float = 1.0
    stop_timeout_sec: float = 10.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceSpec:
        limits_data = data.get("limits", {})
        cwd = data.get("cwd")
        return cls(
            name=data["name"],
            command=data["command"],
            env=data.get("env", {}),
            cwd=Path(cwd) if cwd else None,
            limits=ResourceLimits.from_dict(limits_data),
            enabled=data.get("enabled", True),
            restart=data.get("restart", False),
            restart_delay_sec=data.get("restart_delay_sec", 1.0),
            stop_timeout_sec=data.get("stop_timeout_sec", 10.0),
        )


def _default_pid_file() -> Path:
    """Get default PID file path, preferring user-accessible locations."""
    import os

    # Use /run for root, XDG_RUNTIME_DIR or ~/.local/run for users
    if os.geteuid() == 0:
        return Path("/run/service-manager/agent.pid")
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "service-manager" / "agent.pid"
    return Path.home() / ".local" / "run" / "service-manager" / "agent.pid"


def _default_cgroup_root() -> Path:
    """Get default cgroup root path, preferring BLUEOS_CGROUP_ROOT env var for Docker."""
    import os

    # BLUEOS_CGROUP_ROOT is set by prepare_cgroups in start-blueos-core for Docker environments
    env_root = os.environ.get("BLUEOS_CGROUP_ROOT")
    if env_root:
        return Path(env_root)
    return Path("/sys/fs/cgroup/service-manager")


@dataclass
class AgentConfig:
    """Agent configuration."""

    host: str = "127.0.0.1"
    port: int = 9876
    pid_file: Path = field(default_factory=_default_pid_file)
    cgroup_root: Path = field(default_factory=_default_cgroup_root)
    metrics_interval_sec: float = 1.0
    log_buffer_lines: int = 10000
    services: list[ServiceSpec] = field(default_factory=list)

    @property
    def base_url(self) -> str:
        """Get the base URL for the agent API."""
        return f"http://{self.host}:{self.port}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        agent_data = data.get("agent", {})

        pid_file = agent_data.get("pid_file")
        if pid_file is None:
            pid_file = _default_pid_file()
        else:
            pid_file = Path(pid_file)

        cgroup_root = agent_data.get("cgroup_root")
        if cgroup_root is None:
            cgroup_root = _default_cgroup_root()
        else:
            cgroup_root = Path(cgroup_root)

        services = [ServiceSpec.from_dict(s) for s in data.get("service", [])]

        return cls(
            host=agent_data.get("host", "127.0.0.1"),
            port=agent_data.get("port", 9876),
            pid_file=pid_file,
            cgroup_root=cgroup_root,
            metrics_interval_sec=agent_data.get("metrics_interval_sec", 1.0),
            log_buffer_lines=agent_data.get("log_buffer_lines", 10000),
            services=services,
        )

    @classmethod
    def load(cls, path: Path) -> AgentConfig:
        """Load configuration from TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_or_default(cls, path: Path | None = None) -> AgentConfig:
        """Load configuration from file, or return defaults if not found."""
        if path is None:
            # Try standard locations
            candidates = [
                Path("/etc/service-manager/config.toml"),
                Path.home() / ".config/service-manager/config.toml",
                Path("config.toml"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    return cls.load(candidate)
            return cls()

        if path.exists():
            return cls.load(path)
        return cls()

    def get_service(self, name: str) -> ServiceSpec | None:
        """Get service spec by name."""
        for svc in self.services:
            if svc.name == name:
                return svc
        return None


def _default_overrides_path() -> Path:
    """Get default path for user configuration overrides."""
    import os

    if os.geteuid() == 0:
        return Path("/etc/service-manager/overrides.json")
    return Path.home() / ".config/service-manager/overrides.json"


class ConfigPersistence:
    """Handles saving and loading user configuration overrides."""

    def __init__(self, overrides_path: Path | None = None):
        self.overrides_path = overrides_path or _default_overrides_path()
        self._overrides: dict[str, Any] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load overrides from file if it exists."""
        import json

        if self.overrides_path.exists():
            try:
                self._overrides = json.loads(self.overrides_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._overrides = {}
        else:
            self._overrides = {}

    def _save_overrides(self) -> None:
        """Save overrides to file."""
        import json

        self.overrides_path.parent.mkdir(parents=True, exist_ok=True)
        self.overrides_path.write_text(json.dumps(self._overrides, indent=2), encoding="utf-8")

    def get_service_overrides(self, name: str) -> dict[str, Any]:
        """Get overrides for a specific service."""
        services: dict[str, dict[str, Any]] = self._overrides.get("services", {})
        return services.get(name, {})

    def set_service_override(self, name: str, key: str, value: Any) -> None:
        """Set an override for a service."""
        if "services" not in self._overrides:
            self._overrides["services"] = {}
        if name not in self._overrides["services"]:
            self._overrides["services"][name] = {}
        self._overrides["services"][name][key] = value
        self._save_overrides()

    def clear_service_overrides(self, name: str) -> None:
        """Clear all overrides for a service."""
        services = self._overrides.get("services", {})
        if name in services:
            del services[name]
            self._save_overrides()

    def clear_all_overrides(self) -> None:
        """Clear all service overrides."""
        self._overrides = {}
        self._save_overrides()

    def apply_overrides(self, spec: ServiceSpec) -> None:
        """Apply saved overrides to a service spec."""
        overrides = self.get_service_overrides(spec.name)
        if not overrides:
            return

        if "enabled" in overrides:
            spec.enabled = overrides["enabled"]
        if "command" in overrides:
            spec.command = overrides["command"]
        if "restart" in overrides:
            spec.restart = overrides["restart"]
        if "restart_delay_sec" in overrides:
            spec.restart_delay_sec = overrides["restart_delay_sec"]
        if "stop_timeout_sec" in overrides:
            spec.stop_timeout_sec = overrides["stop_timeout_sec"]
        if "limits" in overrides:
            limits_data = overrides["limits"]
            if "cpu_cores" in limits_data:
                spec.limits.cpu_cores = limits_data["cpu_cores"]
            if "memory_mb" in limits_data:
                spec.limits.memory_mb = limits_data["memory_mb"]
            if "max_pids" in limits_data:
                spec.limits.max_pids = limits_data["max_pids"]
