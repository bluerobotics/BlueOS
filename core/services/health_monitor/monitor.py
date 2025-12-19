from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

Severity = str
Source = str

PROBLEM_DETECTED = "problem_detected"
PROBLEM_RESOLVED = "problem_resolved"
PROBLEM_UPDATED = "problem_updated"


def now_ms() -> int:
    return int(time.time() * 1000)


class HealthProblem(BaseModel):
    id: str
    severity: Severity
    title: str
    details: str
    source: Source
    timestamp: int
    metadata: Optional[Dict[str, Any]] = None
    first_seen_ms: Optional[int] = None
    last_seen_ms: Optional[int] = None


class HealthEvent(HealthProblem):
    type: str


class HealthSummary(BaseModel):
    active: List[HealthProblem] = Field(default_factory=list)
    updated_at: int


class HealthHistory(BaseModel):
    events: List[HealthEvent] = Field(default_factory=list)


@dataclass
class HealthCheckResult:
    active: Dict[str, HealthProblem]
    resolved: Dict[str, HealthProblem]


@dataclass
class ProblemRecord:
    problem: HealthProblem
    first_seen_ms: int
    last_seen_ms: int


class HealthStateTracker:
    def __init__(self) -> None:
        self._active: Dict[str, ProblemRecord] = {}

    def diff_and_update(
        self, new_active: Dict[str, HealthProblem], resolved_info: Dict[str, HealthProblem]
    ) -> List[HealthEvent]:
        events: List[HealthEvent] = []
        now = now_ms()

        # Detect new or updated problems
        for problem_id, problem in new_active.items():
            record = self._active.get(problem_id)
            if record is None:
                record = ProblemRecord(problem=problem, first_seen_ms=problem.timestamp, last_seen_ms=problem.timestamp)
                self._active[problem_id] = record
                events.append(
                    self._event_from_problem(PROBLEM_DETECTED, problem, record.first_seen_ms, record.last_seen_ms)
                )
                continue

            record.last_seen_ms = problem.timestamp
            has_changed = (
                record.problem.severity != problem.severity
                or record.problem.title != problem.title
                or record.problem.details != problem.details
                or record.problem.metadata != problem.metadata
            )
            record.problem = problem
            if has_changed:
                events.append(
                    self._event_from_problem(PROBLEM_UPDATED, problem, record.first_seen_ms, record.last_seen_ms)
                )

        # Detect resolved problems
        for problem_id in list(self._active.keys()):
            if problem_id in new_active:
                continue
            record = self._active.pop(problem_id)
            resolved_problem = resolved_info.get(problem_id)
            if resolved_problem is None:
                resolved_problem = self._build_resolved_problem(record.problem, now)
            events.append(self._event_from_problem(PROBLEM_RESOLVED, resolved_problem, record.first_seen_ms, now))

        return events

    def active_problems(self) -> List[HealthProblem]:
        problems: List[HealthProblem] = []
        for record in self._active.values():
            problem = record.problem.copy(deep=True)
            problem.first_seen_ms = record.first_seen_ms
            problem.last_seen_ms = record.last_seen_ms
            problems.append(problem)
        return sorted(problems, key=lambda item: item.timestamp, reverse=True)

    @staticmethod
    def _event_from_problem(
        event_type: str, problem: HealthProblem, first_seen_ms: int, last_seen_ms: int
    ) -> HealthEvent:
        payload = problem.dict()
        payload["type"] = event_type
        payload["first_seen_ms"] = first_seen_ms
        payload["last_seen_ms"] = last_seen_ms
        return HealthEvent(**payload)

    @staticmethod
    def _build_resolved_problem(problem: HealthProblem, timestamp: int) -> HealthProblem:
        return HealthProblem(
            id=problem.id,
            severity="info",
            title=f"{problem.title} resolved",
            details="The issue is no longer detected.",
            source=problem.source,
            timestamp=timestamp,
            metadata=problem.metadata,
        )


class KernelErrorTracker:
    ERROR_LEVELS = {"err", "crit", "alert", "emerg"}

    def __init__(self, window_ms: int) -> None:
        self._window_ms = window_ms
        self._last_sequence: Optional[int] = None
        self._last_error_ms: Optional[int] = None
        self._last_message: Optional[str] = None
        self._last_level: Optional[str] = None

    def evaluate(self, messages: List[Dict[str, Any]], now: int) -> HealthCheckResult:
        active: Dict[str, HealthProblem] = {}
        resolved: Dict[str, HealthProblem] = {}

        for message in messages:
            sequence = message.get("sequence_number")
            level = str(message.get("level", "")).lower()
            if sequence is None or level not in self.ERROR_LEVELS:
                continue
            if self._last_sequence is None or sequence > self._last_sequence:
                self._last_sequence = sequence
                self._last_error_ms = now
                self._last_message = message.get("message", "")
                self._last_level = level

        if self._last_error_ms is not None and (now - self._last_error_ms) <= self._window_ms:
            details = self._last_message or "Kernel reported an error."
            active["kernel.error"] = HealthProblem(
                id="kernel.error",
                severity="error",
                title="Kernel error detected",
                details=details,
                source="system",
                timestamp=now,
                metadata={
                    "level": self._last_level,
                    "sequence_number": self._last_sequence,
                },
            )
        elif self._last_error_ms is not None:
            resolved["kernel.error"] = HealthProblem(
                id="kernel.error",
                severity="info",
                title="Kernel error resolved",
                details="No new kernel errors detected recently.",
                source="system",
                timestamp=now,
                metadata={
                    "sequence_number": self._last_sequence,
                },
            )

        return HealthCheckResult(active=active, resolved=resolved)


class UsbTracker:
    def __init__(self) -> None:
        self._known_devices: Dict[str, Dict[str, Any]] = {}
        self._disconnected_devices: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def evaluate(self, serial_ports: Dict[str, Any], now: int) -> HealthCheckResult:
        active: Dict[str, HealthProblem] = {}
        resolved: Dict[str, HealthProblem] = {}

        current_devices: Dict[str, Dict[str, Any]] = {}
        ports = serial_ports.get("ports", []) if isinstance(serial_ports, dict) else []
        for port in ports:
            device_key = self._device_key(port)
            if not device_key:
                continue
            current_devices[device_key] = port

        if not self._initialized:
            self._known_devices = current_devices
            self._initialized = True
            return HealthCheckResult(active=active, resolved=resolved)

        removed = set(self._known_devices.keys()) - set(current_devices.keys())
        added = set(current_devices.keys()) - set(self._known_devices.keys())

        for device_key in removed:
            self._disconnected_devices[device_key] = self._known_devices.get(device_key, {})

        for device_key in added:
            if device_key in self._disconnected_devices:
                resolved[self._problem_id(device_key)] = HealthProblem(
                    id=self._problem_id(device_key),
                    severity="info",
                    title="USB device reconnected",
                    details=f"USB device {device_key} connected.",
                    source="system",
                    timestamp=now,
                    metadata={"device": current_devices.get(device_key)},
                )
                self._disconnected_devices.pop(device_key, None)

        for device_key, device in self._disconnected_devices.items():
            active[self._problem_id(device_key)] = HealthProblem(
                id=self._problem_id(device_key),
                severity="warn",
                title="USB device disconnected",
                details=f"USB device {device_key} disconnected.",
                source="system",
                timestamp=now,
                metadata={"device": device},
            )

        self._known_devices = current_devices
        return HealthCheckResult(active=active, resolved=resolved)

    @staticmethod
    def _problem_id(device_key: str) -> str:
        return f"usb.device.{device_key}.disconnected"

    @staticmethod
    def _device_key(port: Dict[str, Any]) -> Optional[str]:
        udev = port.get("udev_properties") or {}
        vendor = UsbTracker._safe_str(udev.get("ID_VENDOR_ID") or udev.get("ID_VENDOR"))
        model = UsbTracker._safe_str(udev.get("ID_MODEL_ID") or udev.get("ID_MODEL"))
        serial = UsbTracker._safe_str(udev.get("ID_SERIAL_SHORT") or udev.get("ID_SERIAL"))
        name = UsbTracker._safe_str(port.get("name"))
        by_path = UsbTracker._safe_str(port.get("by_path"))

        pieces: List[str] = []
        for piece in (vendor, model, serial, name, by_path):
            if piece:
                pieces.append(piece)
        if not pieces:
            return None
        return "_".join(pieces).replace("/", "_")

    @staticmethod
    def _safe_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class VersionComparator:
    @staticmethod
    def fix_version(tag: str) -> Optional[str]:
        if ".beta" in tag:
            tag = tag.replace(".beta", "-beta.")
        if "." not in tag:
            return None
        return tag

    @staticmethod
    def is_semver(tag: str) -> bool:
        return VersionComparator._parse_semver(tag) is not None

    @staticmethod
    def _parse_semver(tag: str) -> Optional[Tuple[int, int, int, Optional[str], Optional[int]]]:
        fixed = VersionComparator.fix_version(tag)
        if fixed is None:
            return None
        main, _, pre = fixed.partition("-")
        parts = main.split(".")
        if len(parts) < 3:
            return None
        try:
            major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
        pre_tag = None
        pre_num = None
        if pre:
            pre_parts = pre.split(".")
            pre_tag = pre_parts[0]
            if len(pre_parts) > 1:
                try:
                    pre_num = int(pre_parts[1])
                except ValueError:
                    pre_num = None
        return major, minor, patch, pre_tag, pre_num

    @staticmethod
    def compare(a: str, b: str) -> int:  # pylint: disable=too-many-return-statements
        parsed_a = VersionComparator._parse_semver(a)
        parsed_b = VersionComparator._parse_semver(b)
        if parsed_a is None or parsed_b is None:
            return 0
        if parsed_a[:3] != parsed_b[:3]:
            return -1 if parsed_a[:3] < parsed_b[:3] else 1
        pre_a, pre_b = parsed_a[3:], parsed_b[3:]
        if pre_a[0] is None and pre_b[0] is None:
            return 0
        if pre_a[0] is None:
            return 1
        if pre_b[0] is None:
            return -1
        if pre_a != pre_b:
            return -1 if pre_a < pre_b else 1
        return 0

    @staticmethod
    def latest_semver(tags: Iterable[str]) -> Optional[str]:
        latest: Optional[str] = None
        for tag in tags:
            if VersionComparator._parse_semver(tag) is None:
                continue
            if latest is None or VersionComparator.compare(tag, latest) > 0:
                latest = tag
        return latest


def evaluate_disk(
    disks: List[Dict[str, Any]], threshold_bytes: int, threshold_percent: float, now: int
) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    root_disk = next((disk for disk in disks if disk.get("mount_point") == "/"), None)
    if root_disk is None:
        return HealthCheckResult(active=active, resolved=resolved)
    total = root_disk.get("total_space_B") or 0
    free = root_disk.get("available_space_B") or 0
    percent_free = (free / total * 100) if total else 0

    problem = HealthProblem(
        id="disk.low_space",
        severity="critical",
        title="Low disk space",
        details=f"Root filesystem is below {threshold_bytes / 2**30:.1f} GB free ({free / 2**30:.1f} GB remaining).",
        source="system",
        timestamp=now,
        metadata={
            "path": "/",
            "free_bytes": free,
            "threshold_bytes": threshold_bytes,
            "free_percent": percent_free,
            "threshold_percent": threshold_percent,
        },
    )

    if free < threshold_bytes or percent_free < threshold_percent:
        active[problem.id] = problem
    else:
        resolved[problem.id] = HealthProblem(
            id=problem.id,
            severity="info",
            title="Low disk space resolved",
            details=f"Root filesystem is above the free-space threshold ({free / 2**30:.1f} GB remaining).",
            source="system",
            timestamp=now,
            metadata=problem.metadata,
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_memory(memory: Dict[str, Any], warn_percent: float, error_percent: float, now: int) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    ram = memory.get("ram") if isinstance(memory, dict) else None
    if not ram:
        return HealthCheckResult(active=active, resolved=resolved)
    total_kb = ram.get("total_kB") or 0
    used_kb = ram.get("used_kB") or 0
    if total_kb <= 0:
        return HealthCheckResult(active=active, resolved=resolved)

    used_percent = used_kb / total_kb * 100.0
    severity = "warn"
    if used_percent >= error_percent:
        severity = "error"

    problem = HealthProblem(
        id="memory.high_usage",
        severity=severity,
        title="High memory usage",
        details=f"RAM usage is at {used_percent:.1f}% ({used_kb / 1024:.1f} MB used).",
        source="system",
        timestamp=now,
        metadata={
            "used_kb": used_kb,
            "total_kb": total_kb,
            "used_percent": used_percent,
            "warn_percent": warn_percent,
            "error_percent": error_percent,
        },
    )

    if used_percent >= warn_percent:
        active[problem.id] = problem
    else:
        resolved[problem.id] = HealthProblem(
            id=problem.id,
            severity="info",
            title="High memory usage resolved",
            details=f"RAM usage is below {warn_percent:.1f}% ({used_percent:.1f}% used).",
            source="system",
            timestamp=now,
            metadata=problem.metadata,
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_sysid_mismatch(vehicle_sysid: Optional[int], container_sysid: int, now: int) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}
    if vehicle_sysid is None:
        return HealthCheckResult(active=active, resolved=resolved)

    problem = HealthProblem(
        id="mavlink.sysid_mismatch",
        severity="warn",
        title="MAVLink SYSID mismatch",
        details=f"Vehicle SYSID ({vehicle_sysid}) differs from BlueOS container SYSID ({container_sysid}).",
        source="vehicle",
        timestamp=now,
        metadata={
            "vehicle_sysid": vehicle_sysid,
            "container_sysid": container_sysid,
        },
    )

    if vehicle_sysid != container_sysid:
        active[problem.id] = problem
    else:
        resolved[problem.id] = HealthProblem(
            id=problem.id,
            severity="info",
            title="MAVLink SYSID mismatch resolved",
            details=f"Vehicle SYSID matches BlueOS container SYSID ({container_sysid}).",
            source="vehicle",
            timestamp=now,
            metadata=problem.metadata,
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_voltage(
    voltage_mv: Optional[float],
    low_volts: float,
    high_volts: float,
    now: int,
) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}
    if voltage_mv is None or voltage_mv <= 0:
        return HealthCheckResult(active=active, resolved=resolved)

    voltage = voltage_mv / 1000.0
    low_problem = HealthProblem(
        id="vehicle.voltage.low",
        severity="warn",
        title="Low voltage detected",
        details=f"Vehicle voltage is {voltage:.2f} V (below {low_volts:.2f} V).",
        source="vehicle",
        timestamp=now,
        metadata={"voltage_v": voltage, "threshold_v": low_volts},
    )
    high_problem = HealthProblem(
        id="vehicle.voltage.high",
        severity="warn",
        title="High voltage detected",
        details=f"Vehicle voltage is {voltage:.2f} V (above {high_volts:.2f} V).",
        source="vehicle",
        timestamp=now,
        metadata={"voltage_v": voltage, "threshold_v": high_volts},
    )

    if voltage < low_volts:
        active[low_problem.id] = low_problem
    else:
        resolved[low_problem.id] = HealthProblem(
            id=low_problem.id,
            severity="info",
            title="Low voltage resolved",
            details=f"Vehicle voltage is {voltage:.2f} V.",
            source="vehicle",
            timestamp=now,
            metadata=low_problem.metadata,
        )

    if voltage > high_volts:
        active[high_problem.id] = high_problem
    else:
        resolved[high_problem.id] = HealthProblem(
            id=high_problem.id,
            severity="info",
            title="High voltage resolved",
            details=f"Vehicle voltage is {voltage:.2f} V.",
            source="vehicle",
            timestamp=now,
            metadata=high_problem.metadata,
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_packet_loss(
    networks: List[Dict[str, Any]],
    error_ratio_threshold: float,
    error_count_threshold: int,
    now: int,
) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    for network in networks:
        if network.get("is_loopback") or not network.get("is_up", True):
            continue
        errors = (network.get("errors_on_received") or 0) + (network.get("errors_on_transmitted") or 0)
        packets = (network.get("packets_received") or 0) + (network.get("packets_transmitted") or 0)
        if packets <= 0:
            continue
        ratio = errors / packets if packets else 0
        interface = network.get("name", "unknown")
        problem_id = f"network.packet_loss.{interface}"
        problem = HealthProblem(
            id=problem_id,
            severity="warn",
            title="Packet loss detected",
            details=f"Interface {interface} reported {errors} errors out of {packets} packets.",
            source="network",
            timestamp=now,
            metadata={
                "interface": interface,
                "errors": errors,
                "packets": packets,
                "error_ratio": ratio,
                "error_ratio_threshold": error_ratio_threshold,
                "error_count_threshold": error_count_threshold,
            },
        )
        if errors >= error_count_threshold and ratio >= error_ratio_threshold:
            active[problem_id] = problem
        else:
            resolved[problem_id] = HealthProblem(
                id=problem_id,
                severity="info",
                title="Packet loss resolved",
                details=f"Interface {interface} error rate is back to normal.",
                source="network",
                timestamp=now,
                metadata=problem.metadata,
            )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_extension_resources(  # pylint: disable=too-many-locals
    extension_stats: Dict[str, Dict[str, Any]],
    cpu_threshold: float,
    memory_threshold: float,
    disk_threshold: float,
    now: int,
) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    for name, stats in extension_stats.items():
        cpu = stats.get("cpu")
        memory = stats.get("memory")
        disk = stats.get("disk")

        cpu_value = cpu if isinstance(cpu, (int, float)) else None
        mem_value = memory if isinstance(memory, (int, float)) else None
        disk_value = disk if isinstance(disk, (int, float)) else None

        over_cpu = cpu_value is not None and cpu_value >= cpu_threshold
        over_mem = mem_value is not None and mem_value >= memory_threshold
        over_disk = disk_value is not None and disk_value >= disk_threshold

        if not (over_cpu or over_mem or over_disk):
            resolved_id = f"extension.resource_hog.{name}"
            resolved[resolved_id] = HealthProblem(
                id=resolved_id,
                severity="info",
                title="Extension resource usage normalized",
                details=f"Extension {name} resource usage is within limits.",
                source="extension",
                timestamp=now,
                metadata=stats,
            )
            continue

        details = f"Extension {name} usage: CPU {cpu_value}%, Memory {mem_value}%, Disk {disk_value}%."
        problem_id = f"extension.resource_hog.{name}"
        active[problem_id] = HealthProblem(
            id=problem_id,
            severity="warn",
            title="Extension using excessive resources",
            details=details,
            source="extension",
            timestamp=now,
            metadata={
                "cpu_percent": cpu_value,
                "memory_percent": mem_value,
                "disk_percent": disk_value,
                "cpu_threshold": cpu_threshold,
                "memory_threshold": memory_threshold,
                "disk_threshold": disk_threshold,
            },
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_factory_mode(is_factory: bool, now: int) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    problem = HealthProblem(
        id="system.factory_mode",
        severity="warn",
        title="Factory mode detected",
        details="BlueOS is running the factory image. This usually indicates an update recovery.",
        source="system",
        timestamp=now,
        metadata={},
    )

    if is_factory:
        active[problem.id] = problem
    else:
        resolved[problem.id] = HealthProblem(
            id=problem.id,
            severity="info",
            title="Factory mode resolved",
            details="BlueOS is no longer running the factory image.",
            source="system",
            timestamp=now,
            metadata={},
        )

    return HealthCheckResult(active=active, resolved=resolved)


def evaluate_update_available(
    current_version: Optional[Dict[str, Any]],
    available_versions: List[Dict[str, Any]],
    problem_id: str,
    title: str,
    now: int,
) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}

    if not current_version:
        return HealthCheckResult(active=active, resolved=resolved)
    current_tag = current_version.get("tag")
    if not current_tag:
        return HealthCheckResult(active=active, resolved=resolved)

    latest_tag = VersionComparator.latest_semver([version.get("tag", "") for version in available_versions])
    update_available = False
    if latest_tag and VersionComparator.compare(latest_tag, current_tag) > 0:
        update_available = True
    current_sha = current_version.get("sha")
    matching = next((version for version in available_versions if version.get("tag") == current_tag), None)
    if matching and current_sha and matching.get("sha") and matching.get("sha") != current_sha:
        update_available = True
        if not latest_tag:
            latest_tag = current_tag

    if update_available:
        active[problem_id] = HealthProblem(
            id=problem_id,
            severity="info",
            title=title,
            details=f"Version {latest_tag} is available (current: {current_tag}).",
            source="system",
            timestamp=now,
            metadata={"current_tag": current_tag, "latest_tag": latest_tag, "current_sha": current_sha},
        )
    else:
        resolved[problem_id] = HealthProblem(
            id=problem_id,
            severity="info",
            title=f"{title} resolved",
            details=f"No newer version detected (current: {current_tag}).",
            source="system",
            timestamp=now,
            metadata={"current_tag": current_tag, "latest_tag": latest_tag, "current_sha": current_sha},
        )

    return HealthCheckResult(active=active, resolved=resolved)


def collect_extension_container_names(extensions: List[Dict[str, Any]]) -> List[str]:
    container_names = []
    for extension in extensions:
        docker_name = extension.get("docker")
        tag = extension.get("tag")
        if not docker_name or not tag:
            continue
        container_names.append(_extension_container_name(docker_name, tag))
    return container_names


def filter_extension_stats(stats: Dict[str, Any], container_names: List[str]) -> Dict[str, Dict[str, Any]]:
    filtered: Dict[str, Dict[str, Any]] = {}
    for container_name in container_names:
        if container_name in stats:
            filtered[container_name] = stats[container_name]
    return filtered


def _extension_container_name(docker: str, tag: str) -> str:
    safe = "".join(ch for ch in f"{docker}{tag}" if ch.isalnum())
    return f"extension-{safe}"


def merge_results(results: Iterable[HealthCheckResult]) -> HealthCheckResult:
    active: Dict[str, HealthProblem] = {}
    resolved: Dict[str, HealthProblem] = {}
    for result in results:
        active.update(result.active)
        resolved.update(result.resolved)
    return HealthCheckResult(active=active, resolved=resolved)
