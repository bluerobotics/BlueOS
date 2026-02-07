"""REST server using FastAPI framework."""
# pylint: disable=global-statement,too-many-statements,too-many-locals,too-many-arguments,too-many-branches

import logging
import sys
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from service_manager import __version__
from service_manager.cgroup import CgroupController
from service_manager.config import ConfigPersistence
from service_manager.metrics import MetricsSampler
from service_manager.output import OutputCapture
from service_manager.registry import ServiceRegistry
from service_manager.supervisor import ProcessSupervisor

log = logging.getLogger(__name__)

# Global references set during app creation
_registry: Optional[ServiceRegistry] = None
_supervisor: Optional[ProcessSupervisor] = None
_output: Optional[OutputCapture] = None
_sampler: Optional[MetricsSampler] = None
_cgroup: Optional[CgroupController] = None
_persistence: Optional[ConfigPersistence] = None


# ----- Request/Response Models -----


class StopServiceBody(BaseModel):
    """Request body for stopping a service."""

    force: Optional[bool] = False


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class ErrorResponse(BaseModel):
    """Error response."""

    error: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    services_running: int
    services_total: int


class VersionResponse(BaseModel):
    """Version response."""

    version: str
    python_version: str


class UpdateLimitsBody(BaseModel):
    """Request body for updating service resource limits."""

    cpu_cores: Optional[float] = None
    memory_mb: Optional[int] = None
    max_pids: Optional[int] = None


class UpdateConfigBody(BaseModel):
    """Request body for updating service configuration."""

    enabled: Optional[bool] = None
    command: Optional[list[str]] = None
    restart: Optional[bool] = None
    restart_delay_sec: Optional[float] = None
    stop_timeout_sec: Optional[float] = None
    limits: Optional[UpdateLimitsBody] = None


# ----- Helper Functions -----


def json_response(data: dict[str, Any]) -> dict[str, Any]:
    """Return data for JSON response."""
    return data


def get_registry() -> ServiceRegistry:
    """Get the service registry, raising HTTPException if not available."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Service registry not initialized")
    return _registry


def get_supervisor() -> ProcessSupervisor:
    """Get the process supervisor, raising HTTPException if not available."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Process supervisor not initialized")
    return _supervisor


def get_output() -> OutputCapture:
    """Get the output capture, raising HTTPException if not available."""
    if _output is None:
        raise HTTPException(status_code=503, detail="Output capture not initialized")
    return _output


def get_sampler() -> MetricsSampler:
    """Get the metrics sampler, raising HTTPException if not available."""
    if _sampler is None:
        raise HTTPException(status_code=503, detail="Metrics sampler not initialized")
    return _sampler


def get_cgroup() -> CgroupController:
    """Get the cgroup controller, raising HTTPException if not available."""
    if _cgroup is None:
        raise HTTPException(status_code=503, detail="Cgroup controller not initialized")
    return _cgroup


def get_persistence() -> ConfigPersistence:
    """Get the config persistence, raising HTTPException if not available."""
    if _persistence is None:
        raise HTTPException(status_code=503, detail="Config persistence not initialized")
    return _persistence


# ----- App Factory -----


def create_app(
    registry: ServiceRegistry,
    supervisor: ProcessSupervisor,
    output: OutputCapture,
    sampler: MetricsSampler,
    cgroup: Optional[CgroupController] = None,
    persistence: Optional[ConfigPersistence] = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    global _registry, _supervisor, _output, _sampler, _cgroup, _persistence
    _registry = registry
    _supervisor = supervisor
    _output = output
    _sampler = sampler
    _cgroup = cgroup
    _persistence = persistence or ConfigPersistence()

    app = FastAPI(
        title="Service Manager API",
        description="Linux service supervisor with cgroups v2 resource control",
        version=__version__,
    )

    # ----- Health & Info Endpoints -----

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health() -> HealthResponse:
        """Health check endpoint."""
        reg = get_registry()
        running = len(reg.running_services())
        total = len(reg.all())
        return HealthResponse(status="healthy", services_running=running, services_total=total)

    @app.get("/version", response_model=VersionResponse, tags=["Health"])
    async def version() -> VersionResponse:
        """Get service-manager version."""
        return VersionResponse(version=__version__, python_version=sys.version)

    # ----- Service Management Endpoints -----

    @app.get("/services", tags=["Services"])
    async def list_services() -> dict[str, Any]:
        """List all registered services with their status."""
        reg = get_registry()
        services = [s.to_dict() for s in reg.all()]
        return {"services": services, "count": len(services)}

    @app.get("/services/{name}", tags=["Services"])
    async def get_service(name: str) -> dict[str, Any]:
        """Get details for a specific service."""
        reg = get_registry()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")
        return state.to_dict()

    @app.post("/services/{name}/start", response_model=MessageResponse, tags=["Services"])
    async def start_service(name: str) -> MessageResponse:
        """Start a stopped service."""
        reg = get_registry()
        sup = get_supervisor()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        if state.is_running:
            return MessageResponse(message=f"Service {name} is already running")

        success = await sup.start_service(name)
        if success:
            return MessageResponse(message=f"Service {name} started")
        raise HTTPException(status_code=500, detail=f"Failed to start service: {name}")

    @app.post("/services/{name}/stop", response_model=MessageResponse, tags=["Services"])
    async def stop_service(name: str, body: Optional[StopServiceBody] = None) -> MessageResponse:
        """Stop a running service."""
        reg = get_registry()
        sup = get_supervisor()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        if not state.is_running:
            return MessageResponse(message=f"Service {name} is not running")

        force = bool(body.force) if body and body.force else False
        success = await sup.stop_service(name, force=force)
        if success:
            return MessageResponse(message=f"Service {name} stopped")
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {name}")

    @app.post("/services/{name}/restart", response_model=MessageResponse, tags=["Services"])
    async def restart_service(name: str) -> MessageResponse:
        """Restart a service (stop then start)."""
        reg = get_registry()
        sup = get_supervisor()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        if state.is_running:
            await sup.stop_service(name)

        success = await sup.start_service(name)
        if success:
            return MessageResponse(message=f"Service {name} restarted")
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {name}")

    @app.patch("/services/{name}/config", response_model=MessageResponse, tags=["Services"])
    async def update_service_config(name: str, body: UpdateConfigBody) -> MessageResponse:
        """Update service configuration (limits, restart settings, enabled, command)."""
        reg = get_registry()
        sup = get_supervisor()
        cg = get_cgroup()
        persist = get_persistence()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        spec = state.spec
        updated_fields = []

        # Update enabled state
        if body.enabled is not None:
            spec.enabled = body.enabled
            persist.set_service_override(name, "enabled", body.enabled)
            updated_fields.append("enabled")
            # Stop service if disabled, start if enabled
            if not body.enabled and state.is_running:
                await sup.stop_service(name)
            elif body.enabled and not state.is_running:
                await sup.start_service(name)

        # Update command (requires restart to take effect)
        if body.command is not None:
            spec.command = body.command
            persist.set_service_override(name, "command", body.command)
            updated_fields.append("command")

        # Update restart settings
        if body.restart is not None:
            spec.restart = body.restart
            persist.set_service_override(name, "restart", body.restart)
            updated_fields.append("restart")

        if body.restart_delay_sec is not None:
            spec.restart_delay_sec = body.restart_delay_sec
            persist.set_service_override(name, "restart_delay_sec", body.restart_delay_sec)
            updated_fields.append("restart_delay_sec")

        if body.stop_timeout_sec is not None:
            spec.stop_timeout_sec = body.stop_timeout_sec
            persist.set_service_override(name, "stop_timeout_sec", body.stop_timeout_sec)
            updated_fields.append("stop_timeout_sec")

        # Update resource limits
        if body.limits:
            limits = spec.limits
            limits_overrides: dict[str, float | int | None] = {}

            if body.limits.cpu_cores is not None:
                limits.cpu_cores = body.limits.cpu_cores if body.limits.cpu_cores > 0 else None
                limits_overrides["cpu_cores"] = limits.cpu_cores
                updated_fields.append("cpu_cores")

            if body.limits.memory_mb is not None:
                limits.memory_mb = body.limits.memory_mb if body.limits.memory_mb > 0 else None
                limits_overrides["memory_mb"] = limits.memory_mb
                updated_fields.append("memory_mb")

            if body.limits.max_pids is not None:
                limits.max_pids = body.limits.max_pids if body.limits.max_pids > 0 else None
                limits_overrides["max_pids"] = limits.max_pids
                updated_fields.append("max_pids")

            if limits_overrides:
                persist.set_service_override(name, "limits", limits_overrides)

            # Apply limits to running service's cgroup if applicable
            if state.is_running and cg.cgroup_exists(name):
                await cg.update_limits(name, limits)

        if not updated_fields:
            return MessageResponse(message=f"No configuration changes for {name}")

        return MessageResponse(message=f"Updated {name}: {', '.join(updated_fields)}")

    @app.post("/services/{name}/reset", response_model=MessageResponse, tags=["Services"])
    async def reset_service_config(name: str) -> MessageResponse:
        """Reset a service's configuration to defaults (removes user overrides)."""
        reg = get_registry()
        persist = get_persistence()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        persist.clear_service_overrides(name)
        return MessageResponse(message=f"Reset configuration for {name} (restart required)")

    @app.post("/services/reset-all", response_model=MessageResponse, tags=["Services"])
    async def reset_all_configs() -> MessageResponse:
        """Reset all service configurations to defaults (removes all user overrides)."""
        persist = get_persistence()
        persist.clear_all_overrides()
        return MessageResponse(message="Reset all service configurations (restart required)")

    # ----- Logs Endpoints -----

    @app.get("/services/{name}/logs", tags=["Logs"])
    async def get_service_logs(
        name: str,
        tail: Optional[int] = Query(default=100, description="Number of lines to return"),
        stream: Optional[str] = Query(default=None, description="Filter by stream (stdout/stderr)"),
    ) -> dict[str, Any]:
        """Get logs for a specific service."""
        reg = get_registry()
        out = get_output()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        service_output = out.get(name)
        if not service_output:
            return {"service": name, "lines": [], "count": 0}
        lines = service_output.get_lines(tail=tail, stream=stream)
        return {
            "service": name,
            "lines": [line.to_dict() for line in lines],
            "count": len(lines),
        }

    # ----- Metrics Endpoints -----

    @app.get("/metrics", tags=["Metrics"])
    async def get_all_metrics() -> dict[str, Any]:
        """Get metrics for all services."""
        samp = get_sampler()
        metrics = samp.get_all()
        return {
            "metrics": {name: m.to_dict() for name, m in metrics.items()},
            "count": len(metrics),
        }

    @app.get("/metrics/{name}", tags=["Metrics"])
    async def get_service_metrics(name: str) -> dict[str, Any]:
        """Get metrics for a specific service."""
        reg = get_registry()
        samp = get_sampler()
        state = reg.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")

        metrics = samp.get(name)
        if not metrics:
            return {"service": name, "metrics": None}
        return {"service": name, "metrics": metrics.to_dict()}

    return app
