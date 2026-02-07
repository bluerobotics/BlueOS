"""Metrics sampler - periodic collection of service metrics."""
# pylint: disable=global-statement,too-many-instance-attributes,too-many-locals,too-many-branches,too-many-statements

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from service_manager.cgroup import CgroupController
    from service_manager.registry import ServiceRegistry

log = logging.getLogger(__name__)

# System clock ticks per second (for CPU time calculation)
_CLK_TCK: int | None = None


def _get_clk_tck() -> int:
    """Get system clock ticks per second."""
    global _CLK_TCK
    if _CLK_TCK is None:
        try:
            _CLK_TCK = os.sysconf("SC_CLK_TCK")
        except (ValueError, OSError):
            _CLK_TCK = 100  # Common default
    return _CLK_TCK


@dataclass
class ServiceMetrics:
    """Computed metrics for a service at a point in time."""

    timestamp: datetime
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    memory_peak_bytes: int = 0
    swap_bytes: int = 0
    swap_peak_bytes: int = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    io_read_rate: float = 0.0  # bytes/sec
    io_write_rate: float = 0.0  # bytes/sec
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0
    net_rx_rate: float = 0.0  # bytes/sec
    net_tx_rate: float = 0.0  # bytes/sec
    pids: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_bytes / (1024 * 1024), 2),
            "memory_peak_mb": round(self.memory_peak_bytes / (1024 * 1024), 2),
            "swap_mb": round(self.swap_bytes / (1024 * 1024), 2),
            "swap_peak_mb": round(self.swap_peak_bytes / (1024 * 1024), 2),
            "io_read_mb": round(self.io_read_bytes / (1024 * 1024), 2),
            "io_write_mb": round(self.io_write_bytes / (1024 * 1024), 2),
            "io_read_rate_mbps": round(self.io_read_rate / (1024 * 1024), 3),
            "io_write_rate_mbps": round(self.io_write_rate / (1024 * 1024), 3),
            "net_rx_mb": round(self.net_rx_bytes / (1024 * 1024), 2),
            "net_tx_mb": round(self.net_tx_bytes / (1024 * 1024), 2),
            "net_rx_rate_mbps": round(self.net_rx_rate / (1024 * 1024), 3),
            "net_tx_rate_mbps": round(self.net_tx_rate / (1024 * 1024), 3),
            "pids": self.pids,
        }


@dataclass
class PreviousSample:
    """Previous sample for computing deltas."""

    timestamp: float  # time.monotonic()
    cpu_usage_usec: int
    io_read_bytes: int
    io_write_bytes: int
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0


@dataclass
class PeakValues:
    """Tracked peak values for a service."""

    memory_bytes: int = 0
    swap_bytes: int = 0


class MetricsSampler:
    """Periodic metrics collection for running services."""

    def __init__(
        self,
        registry: ServiceRegistry,
        cgroup: CgroupController,
        interval_sec: float = 1.0,
    ):
        self._registry = registry
        self._cgroup = cgroup
        self._interval = interval_sec
        self._current: dict[str, ServiceMetrics] = {}
        self._previous: dict[str, PreviousSample] = {}
        self._peaks: dict[str, PeakValues] = {}

    async def run(self, shutdown_event: asyncio.Event) -> None:
        """Main sampling loop."""
        log.debug(f"Starting metrics sampler with {self._interval}s interval")

        while not shutdown_event.is_set():
            try:
                await self._sample_all()
            except Exception as e:
                log.error(f"Error in metrics sampling: {e}")

            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=self._interval,
                )
            except asyncio.TimeoutError:
                pass

        log.debug("Metrics sampler stopped")

    async def _sample_all(self) -> None:
        """Sample metrics for all running services."""
        running = self._registry.running_services()

        # Clean up old entries for stopped services
        running_names = {s.spec.name for s in running}
        for name in list(self._current.keys()):
            if name not in running_names:
                del self._current[name]
                self._previous.pop(name, None)
                self._peaks.pop(name, None)

        # Sample each running service
        for state in running:
            name = state.spec.name
            metrics = await self._sample_service(name)
            if metrics:
                self._current[name] = metrics

    async def _sample_service(self, name: str) -> ServiceMetrics | None:
        """Sample metrics for a single service."""
        state = self._registry.get(name)
        pid = state.pid if state else None

        # Try cgroup metrics first
        cgroup_metrics = await self._cgroup.read_metrics(name)
        if cgroup_metrics is not None:
            return self._compute_cgroup_metrics(name, cgroup_metrics, pid)

        # Fallback to /proc-based metrics
        if pid is None:
            return None

        return await self._sample_from_proc(name, pid)

    def _read_net_stats(self, pid: int | None) -> tuple[int, int]:
        """Read network stats from /proc/{pid}/net/dev. Returns (rx_bytes, tx_bytes)."""
        if pid is None:
            return 0, 0

        net_path = Path(f"/proc/{pid}/net/dev")
        if not net_path.exists():
            return 0, 0

        rx_total = 0
        tx_total = 0
        try:
            content = net_path.read_text(encoding="utf-8")
            for line in content.splitlines()[2:]:  # Skip header lines
                parts = line.split()
                if len(parts) < 10:
                    continue
                iface = parts[0].rstrip(":")
                # Skip loopback
                if iface == "lo":
                    continue
                rx_total += int(parts[1])  # rx_bytes
                tx_total += int(parts[9])  # tx_bytes
        except (OSError, IndexError, ValueError):
            pass
        return rx_total, tx_total

    def _compute_cgroup_metrics(  # type: ignore[no-untyped-def]
        self, name: str, cgroup_metrics, pid: int | None
    ) -> ServiceMetrics:
        """Compute metrics from cgroup data."""
        now = time.monotonic()
        prev = self._previous.get(name)

        # Read network stats
        net_rx_bytes, net_tx_bytes = self._read_net_stats(pid)

        # Compute CPU percentage (delta usage / delta time)
        cpu_percent = 0.0
        if prev:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                cpu_delta_usec = cgroup_metrics.cpu_usage_usec - prev.cpu_usage_usec
                cpu_percent = (cpu_delta_usec / 1_000_000) / time_delta_sec * 100

        # Compute IO rates
        io_read_rate = 0.0
        io_write_rate = 0.0
        if prev:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                io_read_rate = (cgroup_metrics.io_read_bytes - prev.io_read_bytes) / time_delta_sec
                io_write_rate = (cgroup_metrics.io_write_bytes - prev.io_write_bytes) / time_delta_sec

        # Compute network rates
        net_rx_rate = 0.0
        net_tx_rate = 0.0
        if prev:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                net_rx_rate = (net_rx_bytes - prev.net_rx_bytes) / time_delta_sec
                net_tx_rate = (net_tx_bytes - prev.net_tx_bytes) / time_delta_sec

        # Store current as previous for next sample
        self._previous[name] = PreviousSample(
            timestamp=now,
            cpu_usage_usec=cgroup_metrics.cpu_usage_usec,
            io_read_bytes=cgroup_metrics.io_read_bytes,
            io_write_bytes=cgroup_metrics.io_write_bytes,
            net_rx_bytes=net_rx_bytes,
            net_tx_bytes=net_tx_bytes,
        )

        # Track peaks ourselves if cgroups don't provide them
        peaks = self._peaks.setdefault(name, PeakValues())
        peaks.memory_bytes = max(peaks.memory_bytes, cgroup_metrics.memory_current)
        peaks.swap_bytes = max(peaks.swap_bytes, cgroup_metrics.swap_current)

        # Use cgroup peaks if available, otherwise use our tracked peaks
        memory_peak = cgroup_metrics.memory_peak if cgroup_metrics.memory_peak > 0 else peaks.memory_bytes
        swap_peak = cgroup_metrics.swap_peak if cgroup_metrics.swap_peak > 0 else peaks.swap_bytes

        return ServiceMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=max(0.0, cpu_percent),
            memory_bytes=cgroup_metrics.memory_current,
            memory_peak_bytes=memory_peak,
            swap_bytes=cgroup_metrics.swap_current,
            swap_peak_bytes=swap_peak,
            io_read_bytes=cgroup_metrics.io_read_bytes,
            io_write_bytes=cgroup_metrics.io_write_bytes,
            io_read_rate=max(0.0, io_read_rate),
            io_write_rate=max(0.0, io_write_rate),
            net_rx_bytes=net_rx_bytes,
            net_tx_bytes=net_tx_bytes,
            net_rx_rate=max(0.0, net_rx_rate),
            net_tx_rate=max(0.0, net_tx_rate),
            pids=cgroup_metrics.pids_current,
        )

    async def _sample_from_proc(self, name: str, pid: int) -> ServiceMetrics | None:
        """Fallback: sample metrics from /proc when cgroups unavailable."""
        proc_path = Path(f"/proc/{pid}")
        if not proc_path.exists():
            return None

        now = time.monotonic()
        prev = self._previous.get(name)

        # Read CPU time from /proc/<pid>/stat
        cpu_usage_usec = 0
        try:
            stat_content = (proc_path / "stat").read_text()
            # Format: pid (comm) state ppid ... utime stime ...
            # Fields 14 and 15 (0-indexed: 13, 14) are utime and stime in clock ticks
            parts = stat_content.split(")")[-1].split()
            utime = int(parts[11])  # Index after (comm) parsing
            stime = int(parts[12])
            clk_tck = _get_clk_tck()
            # Convert clock ticks to microseconds
            cpu_usage_usec = int((utime + stime) * 1_000_000 / clk_tck)
        except (OSError, IndexError, ValueError):
            pass

        # Read memory from /proc/<pid>/statm
        memory_bytes = 0
        try:
            statm_content = (proc_path / "statm").read_text()
            # First field is total pages, second is resident pages
            parts = statm_content.split()
            resident_pages = int(parts[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            memory_bytes = resident_pages * page_size
        except (OSError, IndexError, ValueError):
            pass

        # Read IO from /proc/<pid>/io (may require permissions)
        io_read_bytes = 0
        io_write_bytes = 0
        try:
            io_content = (proc_path / "io").read_text()
            for line in io_content.splitlines():
                if line.startswith("read_bytes:"):
                    io_read_bytes = int(line.split()[1])
                elif line.startswith("write_bytes:"):
                    io_write_bytes = int(line.split()[1])
        except (OSError, PermissionError):
            pass  # /proc/<pid>/io often requires same-user or root

        # Read swap from /proc/<pid>/status (VmSwap field)
        swap_bytes = 0
        try:
            status_content = (proc_path / "status").read_text()
            for line in status_content.splitlines():
                if line.startswith("VmSwap:"):
                    # Format: "VmSwap:    1234 kB"
                    parts = line.split()
                    if len(parts) >= 2:
                        swap_bytes = int(parts[1]) * 1024  # Convert kB to bytes
                    break
        except (OSError, IndexError, ValueError):
            pass

        # Read network stats
        net_rx_bytes, net_tx_bytes = self._read_net_stats(pid)

        # Compute CPU percentage
        cpu_percent = 0.0
        if prev and prev.cpu_usage_usec > 0:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                cpu_delta_usec = cpu_usage_usec - prev.cpu_usage_usec
                cpu_percent = (cpu_delta_usec / 1_000_000) / time_delta_sec * 100

        # Compute IO rates
        io_read_rate = 0.0
        io_write_rate = 0.0
        if prev:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                io_read_rate = (io_read_bytes - prev.io_read_bytes) / time_delta_sec
                io_write_rate = (io_write_bytes - prev.io_write_bytes) / time_delta_sec

        # Compute network rates
        net_rx_rate = 0.0
        net_tx_rate = 0.0
        if prev:
            time_delta_sec = now - prev.timestamp
            if time_delta_sec > 0:
                net_rx_rate = (net_rx_bytes - prev.net_rx_bytes) / time_delta_sec
                net_tx_rate = (net_tx_bytes - prev.net_tx_bytes) / time_delta_sec

        # Store current as previous for next sample
        self._previous[name] = PreviousSample(
            timestamp=now,
            cpu_usage_usec=cpu_usage_usec,
            io_read_bytes=io_read_bytes,
            io_write_bytes=io_write_bytes,
            net_rx_bytes=net_rx_bytes,
            net_tx_bytes=net_tx_bytes,
        )

        # Track peaks ourselves since /proc doesn't provide them
        peaks = self._peaks.setdefault(name, PeakValues())
        peaks.memory_bytes = max(peaks.memory_bytes, memory_bytes)
        peaks.swap_bytes = max(peaks.swap_bytes, swap_bytes)

        return ServiceMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=max(0.0, cpu_percent),
            memory_bytes=memory_bytes,
            memory_peak_bytes=peaks.memory_bytes,
            swap_bytes=swap_bytes,
            swap_peak_bytes=peaks.swap_bytes,
            io_read_bytes=io_read_bytes,
            io_write_bytes=io_write_bytes,
            io_read_rate=max(0.0, io_read_rate),
            io_write_rate=max(0.0, io_write_rate),
            net_rx_bytes=net_rx_bytes,
            net_tx_bytes=net_tx_bytes,
            net_rx_rate=max(0.0, net_rx_rate),
            net_tx_rate=max(0.0, net_tx_rate),
            pids=1,  # Just the main process; can't easily count children
        )

    def get(self, name: str) -> ServiceMetrics | None:
        """Get latest metrics for a service."""
        return self._current.get(name)

    def get_all(self) -> dict[str, ServiceMetrics]:
        """Get latest metrics for all services."""
        return dict(self._current)

    def to_dict(self) -> dict[str, Any]:
        """Get all metrics as JSON-serializable dict."""
        return {name: m.to_dict() for name, m in self._current.items()}
