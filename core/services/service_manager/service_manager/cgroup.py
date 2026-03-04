"""cgroup v2 controller for resource limits and metrics."""
# pylint: disable=too-many-instance-attributes

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from service_manager.config import ResourceLimits

log = logging.getLogger(__name__)


@dataclass
class CgroupMetrics:
    """Metrics read from cgroup."""

    cpu_usage_usec: int = 0
    memory_current: int = 0
    memory_peak: int = 0
    swap_current: int = 0
    swap_peak: int = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    pids_current: int = 0


class CgroupController:
    """Manages cgroup v2 hierarchy for services."""

    def __init__(self, root: Path):
        self.root = root

    def _cgroup_path(self, name: str) -> Path:
        """Get cgroup directory path for a service."""
        return self.root / f"svc-{name}"

    async def ensure_root(self) -> None:
        """Ensure the root cgroup directory exists."""
        if not self.root.exists():
            log.info(f"Creating cgroup root: {self.root}")
            try:
                self.root.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                log.warning(
                    f"Cannot create cgroup root {self.root}. "
                    "Running without cgroup support. "
                    "Run as root or configure systemd delegation."
                )

    async def create(self, name: str, limits: ResourceLimits) -> Path | None:
        """Create cgroup for a service and apply limits."""
        path = self._cgroup_path(name)

        if not self.root.exists():
            log.debug(f"cgroup root not available, skipping cgroup for {name}")
            return None

        try:
            path.mkdir(exist_ok=True)
            await self._apply_limits(path, limits)
            log.debug(f"Created cgroup: {path}")
            return path
        except PermissionError as e:
            log.warning(f"Cannot create cgroup for {name}: {e}")
            return None
        except OSError as e:
            log.error(f"Failed to create cgroup for {name}: {e}")
            return None

    async def _apply_limits(self, path: Path, limits: ResourceLimits) -> None:
        """Apply resource limits to a cgroup."""
        # CPU limit: cpu.max format is "quota period" in microseconds
        # e.g., "150000 100000" means 1.5 cores (150ms per 100ms period)
        if limits.cpu_cores is not None:
            quota = int(limits.cpu_cores * 100000)
            period = 100000
            self._write_file(path / "cpu.max", f"{quota} {period}")

        # Memory limit
        if limits.memory_mb is not None:
            memory_bytes = limits.memory_mb * 1024 * 1024
            self._write_file(path / "memory.max", str(memory_bytes))

        # PID limit
        if limits.max_pids is not None:
            self._write_file(path / "pids.max", str(limits.max_pids))

        # IO limits (requires knowing the device major:minor)
        if limits.io_read_mbps is not None or limits.io_write_mbps is not None:
            log.debug("IO bandwidth limits require device specification, skipping")

    def _write_file(self, path: Path, value: str) -> None:
        """Write a value to a cgroup control file."""
        try:
            path.write_text(value)
        except PermissionError:
            log.warning(f"Cannot write to {path}: permission denied")
        except OSError as e:
            log.warning(f"Cannot write to {path}: {e}")

    def _read_file(self, path: Path) -> str:
        """Read a cgroup control file."""
        try:
            return path.read_text().strip()
        except (OSError, FileNotFoundError):
            return ""

    async def add_pid(self, name: str, pid: int) -> bool:
        """Add a process to a service's cgroup."""
        path = self._cgroup_path(name)
        procs_file = path / "cgroup.procs"

        if not procs_file.exists():
            return False

        try:
            procs_file.write_text(str(pid))
            log.debug(f"Added PID {pid} to cgroup {name}")
            return True
        except OSError as e:
            log.warning(f"Cannot add PID {pid} to cgroup {name}: {e}")
            return False

    async def destroy(self, name: str) -> None:
        """Remove a service's cgroup."""
        path = self._cgroup_path(name)

        if not path.exists():
            return

        # Kill any remaining processes
        procs_file = path / "cgroup.procs"
        if procs_file.exists():
            pids = self._read_file(procs_file).split()
            for pid_str in pids:
                try:
                    os.kill(int(pid_str), 9)
                except (OSError, ValueError):
                    pass

        # Remove the cgroup directory
        try:
            path.rmdir()
            log.debug(f"Destroyed cgroup: {path}")
        except OSError as e:
            log.warning(f"Cannot remove cgroup {path}: {e}")

    # pylint: disable=too-many-branches,too-many-statements
    async def read_metrics(self, name: str) -> CgroupMetrics | None:
        """Read current metrics from a service's cgroup."""
        path = self._cgroup_path(name)

        if not path.exists():
            return None

        metrics = CgroupMetrics()

        # CPU usage from cpu.stat
        cpu_stat = self._read_file(path / "cpu.stat")
        for line in cpu_stat.splitlines():
            if line.startswith("usage_usec"):
                try:
                    metrics.cpu_usage_usec = int(line.split()[1])
                except (IndexError, ValueError):
                    pass

        # Memory
        memory_current = self._read_file(path / "memory.current")
        if memory_current:
            try:
                metrics.memory_current = int(memory_current)
            except ValueError:
                pass

        memory_peak = self._read_file(path / "memory.peak")
        if memory_peak:
            try:
                metrics.memory_peak = int(memory_peak)
            except ValueError:
                pass

        # Swap usage
        swap_current = self._read_file(path / "memory.swap.current")
        if swap_current:
            try:
                metrics.swap_current = int(swap_current)
            except ValueError:
                pass

        swap_peak = self._read_file(path / "memory.swap.peak")
        if swap_peak:
            try:
                metrics.swap_peak = int(swap_peak)
            except ValueError:
                pass

        # IO stats from io.stat
        io_stat = self._read_file(path / "io.stat")
        for line in io_stat.splitlines():
            parts = line.split()
            for part in parts:
                if part.startswith("rbytes="):
                    try:
                        metrics.io_read_bytes += int(part.split("=")[1])
                    except (IndexError, ValueError):
                        pass
                elif part.startswith("wbytes="):
                    try:
                        metrics.io_write_bytes += int(part.split("=")[1])
                    except (IndexError, ValueError):
                        pass

        # PIDs
        pids_current = self._read_file(path / "pids.current")
        if pids_current:
            try:
                metrics.pids_current = int(pids_current)
            except ValueError:
                pass

        return metrics

    async def list_existing(self) -> list[str]:
        """List existing service cgroups (for orphan detection)."""
        if not self.root.exists():
            return []

        result = []
        try:
            for entry in self.root.iterdir():
                if entry.is_dir() and entry.name.startswith("svc-"):
                    result.append(entry.name[4:])  # Strip "svc-" prefix
        except OSError:
            pass
        return result

    async def get_pids(self, name: str) -> list[int]:
        """Get PIDs in a service's cgroup."""
        path = self._cgroup_path(name)
        procs_file = path / "cgroup.procs"

        if not procs_file.exists():
            return []

        pids = []
        content = self._read_file(procs_file)
        for pid_str in content.split():
            try:
                pids.append(int(pid_str))
            except ValueError:
                pass
        return pids

    def cgroup_exists(self, name: str) -> bool:
        """Check if a cgroup exists for a service."""
        return self._cgroup_path(name).exists()

    async def update_limits(self, name: str, limits: ResourceLimits) -> bool:
        """Update limits for an existing cgroup (live update)."""
        path = self._cgroup_path(name)

        if not path.exists():
            log.debug(f"cgroup for {name} does not exist, cannot update limits")
            return False

        try:
            await self._apply_limits(path, limits)
            log.info(f"Updated cgroup limits for {name}")
            return True
        except Exception as e:
            log.error(f"Failed to update cgroup limits for {name}: {e}")
            return False
