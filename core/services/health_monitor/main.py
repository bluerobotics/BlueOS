#! /usr/bin/env python3

import asyncio
import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional

import aiohttp
import zenoh
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from commonwealth.utils.zenoh_helper import ZenohSession
from fastapi import APIRouter, FastAPI, Query, status
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from monitor import (
    HealthEvent,
    HealthHistory,
    HealthStateTracker,
    HealthSummary,
    KernelErrorTracker,
    UsbTracker,
    collect_extension_container_names,
    evaluate_disk,
    evaluate_extension_resources,
    evaluate_factory_mode,
    evaluate_memory,
    evaluate_packet_loss,
    evaluate_sysid_mismatch,
    evaluate_update_available,
    evaluate_voltage,
    merge_results,
    now_ms,
)
from pydantic import BaseModel
from uvicorn import Config, Server

SERVICE_NAME = "health-monitor"
PORT = 9152

LINUX2REST_BASE = "http://127.0.0.1:6030"
KRAKEN_BASE = "http://127.0.0.1:9134"
VERSION_CHOOSER_BASE = "http://127.0.0.1:8081/v1.0"

EVENT_TOPIC = f"services/{SERVICE_NAME}/events"

DEFAULT_CHECK_INTERVAL = float(os.getenv("HEALTH_MONITOR_INTERVAL_SEC", "10"))
DEFAULT_HISTORY_LIMIT = int(os.getenv("HEALTH_MONITOR_HISTORY_LIMIT", "500"))

DISK_FREE_BYTES_THRESHOLD = int(os.getenv("HEALTH_MONITOR_DISK_FREE_BYTES", str(2 * 1024**3)))
DISK_FREE_PERCENT_THRESHOLD = float(os.getenv("HEALTH_MONITOR_DISK_FREE_PERCENT", "10"))

MEMORY_WARN_PERCENT = float(os.getenv("HEALTH_MONITOR_MEMORY_WARN_PERCENT", "90"))
MEMORY_ERROR_PERCENT = float(os.getenv("HEALTH_MONITOR_MEMORY_ERROR_PERCENT", "95"))

KERNEL_ERROR_WINDOW_MS = int(os.getenv("HEALTH_MONITOR_KERNEL_WINDOW_MS", str(10 * 60 * 1000)))

PACKET_LOSS_ERROR_RATIO = float(os.getenv("HEALTH_MONITOR_PACKET_LOSS_RATIO", "0.02"))
PACKET_LOSS_ERROR_COUNT = int(os.getenv("HEALTH_MONITOR_PACKET_LOSS_COUNT", "10"))

EXTENSION_CPU_THRESHOLD = float(os.getenv("HEALTH_MONITOR_EXTENSION_CPU_PERCENT", "80"))
EXTENSION_MEMORY_THRESHOLD = float(os.getenv("HEALTH_MONITOR_EXTENSION_MEMORY_PERCENT", "80"))
EXTENSION_DISK_THRESHOLD = float(os.getenv("HEALTH_MONITOR_EXTENSION_DISK_PERCENT", "80"))

VEHICLE_VOLTAGE_LOW = float(os.getenv("HEALTH_MONITOR_VOLTAGE_LOW", "10.5"))
VEHICLE_VOLTAGE_HIGH = float(os.getenv("HEALTH_MONITOR_VOLTAGE_HIGH", "16.8"))

CONTAINER_SYSID = int(os.getenv("MAV_SYSTEM_ID", "1"))

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Health Monitor service")


class HealthConfig(BaseModel):
    interval_sec: float
    history_limit: int
    disk_free_bytes: int
    disk_free_percent: float
    memory_warn_percent: float
    memory_error_percent: float
    kernel_error_window_ms: int
    packet_loss_ratio: float
    packet_loss_count: int
    extension_cpu_percent: float
    extension_memory_percent: float
    extension_disk_percent: float
    voltage_low: float
    voltage_high: float


class HealthMonitor:  # pylint: disable=too-many-instance-attributes
    def __init__(self) -> None:
        self._state = HealthStateTracker()
        self._history: deque[HealthEvent] = deque(maxlen=DEFAULT_HISTORY_LIMIT)
        self._kernel_tracker = KernelErrorTracker(KERNEL_ERROR_WINDOW_MS)
        self._usb_tracker = UsbTracker()
        self._zenoh = ZenohSession(SERVICE_NAME)
        self._mavlink = MavlinkMessenger()
        self._stop_event = asyncio.Event()
        self._http_session: Optional[aiohttp.ClientSession] = None

    def stop(self) -> None:
        self._stop_event.set()
        self._zenoh.close()
        if self._http_session and not self._http_session.closed:
            asyncio.create_task(self._http_session.close())

    async def run(self) -> None:
        while not self._stop_event.is_set():
            await self.evaluate_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=DEFAULT_CHECK_INTERVAL)
            except asyncio.TimeoutError:
                continue

    async def evaluate_once(self) -> None:  # pylint: disable=too-many-locals
        now = now_ms()
        checks: List[Any] = []

        disks = await self._fetch_json(f"{LINUX2REST_BASE}/system/disk")
        if isinstance(disks, list):
            checks.append(evaluate_disk(disks, DISK_FREE_BYTES_THRESHOLD, DISK_FREE_PERCENT_THRESHOLD, now))

        memory = await self._fetch_json(f"{LINUX2REST_BASE}/system/memory")
        if isinstance(memory, dict):
            checks.append(evaluate_memory(memory, MEMORY_WARN_PERCENT, MEMORY_ERROR_PERCENT, now))

        kernel_buffer = await self._fetch_json(f"{LINUX2REST_BASE}/kernel_buffer")
        if isinstance(kernel_buffer, list):
            checks.append(self._kernel_tracker.evaluate(kernel_buffer, now))

        serial_ports = await self._fetch_json(f"{LINUX2REST_BASE}/serial?udev=true")
        if isinstance(serial_ports, dict):
            checks.append(self._usb_tracker.evaluate(serial_ports, now))

        networks = await self._fetch_json(f"{LINUX2REST_BASE}/system/network")
        if isinstance(networks, list):
            checks.append(evaluate_packet_loss(networks, PACKET_LOSS_ERROR_RATIO, PACKET_LOSS_ERROR_COUNT, now))

        kraken_extensions = await self._fetch_json(f"{KRAKEN_BASE}/v1.0/installed_extensions")
        kraken_stats = await self._fetch_json(f"{KRAKEN_BASE}/v1.0/stats")
        if isinstance(kraken_extensions, list) and isinstance(kraken_stats, dict):
            extension_names = collect_extension_container_names(kraken_extensions)
            extension_stats = {name: kraken_stats.get(name, {}) for name in extension_names}
            checks.append(
                evaluate_extension_resources(
                    extension_stats,
                    EXTENSION_CPU_THRESHOLD,
                    EXTENSION_MEMORY_THRESHOLD,
                    EXTENSION_DISK_THRESHOLD,
                    now,
                )
            )

        vehicle_sysid = await self._get_vehicle_sysid()
        checks.append(evaluate_sysid_mismatch(vehicle_sysid, CONTAINER_SYSID, now))

        voltage_mv = await self._get_vehicle_voltage(vehicle_sysid)
        checks.append(evaluate_voltage(voltage_mv, VEHICLE_VOLTAGE_LOW, VEHICLE_VOLTAGE_HIGH, now))

        factory_mode = await self._is_factory_mode()
        checks.append(evaluate_factory_mode(factory_mode, now))

        core_current = await self._fetch_json(f"{VERSION_CHOOSER_BASE}/version/current")
        core_available = await self._fetch_json(f"{VERSION_CHOOSER_BASE}/version/available/bluerobotics/blueos-core")
        if isinstance(core_available, dict):
            core_available_versions = core_available.get("remote", [])
        else:
            core_available_versions = []
        checks.append(
            evaluate_update_available(
                core_current if isinstance(core_current, dict) else None,
                core_available_versions,
                "updates.blueos_core.available",
                "BlueOS update available",
                now,
            )
        )

        bootstrap_current_tag = await self._bootstrap_tag()
        bootstrap_available = await self._fetch_json(
            f"{VERSION_CHOOSER_BASE}/version/available/bluerobotics/blueos-bootstrap"
        )
        if isinstance(bootstrap_available, dict):
            bootstrap_versions = bootstrap_available.get("remote", [])
        else:
            bootstrap_versions = []
        if bootstrap_current_tag:
            checks.append(
                evaluate_update_available(
                    {"tag": bootstrap_current_tag},
                    bootstrap_versions,
                    "updates.bootstrap.available",
                    "Bootstrap update available",
                    now,
                )
            )

        # TODO(health_monitor): needs source - corrupt configuration files detection.
        # TODO(health_monitor): needs source - vehicle calibration status.
        # TODO(health_monitor): needs source - extension-published warnings channel.
        # TODO(health_monitor): needs source - output channel routing.

        merged = merge_results(checks)
        events = self._state.diff_and_update(merged.active, merged.resolved)
        for event in events:
            self._publish_event(event)
            self._history.append(event)

    def summary(self) -> HealthSummary:
        return HealthSummary(active=self._state.active_problems(), updated_at=now_ms())

    def history_view(self, limit: int) -> HealthHistory:
        events = list(self._history)[-limit:]
        return HealthHistory(events=events)

    def config(self) -> HealthConfig:
        return HealthConfig(
            interval_sec=DEFAULT_CHECK_INTERVAL,
            history_limit=DEFAULT_HISTORY_LIMIT,
            disk_free_bytes=DISK_FREE_BYTES_THRESHOLD,
            disk_free_percent=DISK_FREE_PERCENT_THRESHOLD,
            memory_warn_percent=MEMORY_WARN_PERCENT,
            memory_error_percent=MEMORY_ERROR_PERCENT,
            kernel_error_window_ms=KERNEL_ERROR_WINDOW_MS,
            packet_loss_ratio=PACKET_LOSS_ERROR_RATIO,
            packet_loss_count=PACKET_LOSS_ERROR_COUNT,
            extension_cpu_percent=EXTENSION_CPU_THRESHOLD,
            extension_memory_percent=EXTENSION_MEMORY_THRESHOLD,
            extension_disk_percent=EXTENSION_DISK_THRESHOLD,
            voltage_low=VEHICLE_VOLTAGE_LOW,
            voltage_high=VEHICLE_VOLTAGE_HIGH,
        )

    async def _fetch_json(self, url: str, timeout: float = 2.0) -> Any:
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        try:
            async with self._http_session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as error:
            logger.debug(f"Failed to fetch {url}: {error}")
            return None

    async def _get_vehicle_sysid(self) -> Optional[int]:
        try:
            return await self._mavlink.get_most_recent_vehicle_id()
        except Exception as error:
            logger.debug(f"Failed to fetch vehicle SYSID: {error}")
            return None

    async def _get_vehicle_voltage(self, vehicle_sysid: Optional[int]) -> Optional[float]:
        if vehicle_sysid is None:
            return None
        try:
            message = await self._mavlink.get_mavlink_message("SYS_STATUS", vehicle_sysid, 1)
            payload = message.get("message", {}) if isinstance(message, dict) else {}
            voltage = payload.get("voltage_battery")
            if isinstance(voltage, (int, float)):
                return float(voltage)
            return None
        except Exception as error:
            logger.debug(f"Failed to fetch vehicle voltage: {error}")
            return None

    async def _is_factory_mode(self) -> bool:
        current = await self._fetch_json(f"{VERSION_CHOOSER_BASE}/version/current")
        if isinstance(current, dict):
            return current.get("tag") == "factory"
        return False

    async def _bootstrap_tag(self) -> Optional[str]:
        current = await self._fetch_json(f"{VERSION_CHOOSER_BASE}/bootstrap/current")
        if isinstance(current, str) and ":" in current:
            return current.split(":")[-1]
        if isinstance(current, str):
            return current
        return None

    def _publish_event(self, event: BaseModel) -> None:
        session = self._zenoh.session
        if session is None:
            return
        payload = event.json()
        try:
            session.put(EVENT_TOPIC, payload, encoding=zenoh.Encoding.APPLICATION_JSON)
        except Exception as error:
            logger.debug(f"Failed to publish event: {error}")


health_router = APIRouter(
    prefix="/health",
    tags=["health_monitor_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

monitor = HealthMonitor()


@health_router.get("/summary", response_model=HealthSummary, summary="Return active health issues.")
async def get_summary() -> HealthSummary:
    return monitor.summary()


@health_router.get("/history", response_model=HealthHistory, summary="Return recent health events.")
async def get_history(limit: int = Query(200, ge=1, le=1000)) -> HealthHistory:
    return monitor.history_view(limit)


@health_router.get("/config", response_model=HealthConfig, summary="Return health monitor configuration.")
async def get_config() -> HealthConfig:
    return monitor.config()


fast_api_app = FastAPI(
    title="Health Monitor API",
    description="Monitor system and vehicle health and emit events.",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute
fast_api_app.include_router(health_router)

app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"service": SERVICE_NAME}


@app.on_event("startup")
async def start_background_tasks() -> None:
    asyncio.create_task(monitor.run())


@app.on_event("shutdown")
async def shutdown_background_tasks() -> None:
    monitor.stop()


async def main() -> None:
    try:
        await init_sentry_async(SERVICE_NAME)

        config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
        server = Server(config)

        await server.serve()
    finally:
        logger.info("Health Monitor service stopped")


if __name__ == "__main__":
    asyncio.run(main())
