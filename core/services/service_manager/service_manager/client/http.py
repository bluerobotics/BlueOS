"""HTTP client for service-manager API."""

from __future__ import annotations

from typing import Any, cast

import httpx
from service_manager.config import AgentConfig


class ServiceManagerClient:
    """HTTP client for the service-manager API."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        if base_url is None:
            config = AgentConfig.load_or_default()
            base_url = config.base_url

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        """Create a new HTTP client."""
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def health(self) -> dict[str, Any]:
        """Check daemon health."""
        with self._client() as client:
            response = client.get("/health")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def version(self) -> dict[str, Any]:
        """Get daemon version."""
        with self._client() as client:
            response = client.get("/version")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def list_services(self) -> dict[str, Any]:
        """List all services."""
        with self._client() as client:
            response = client.get("/services")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def get_service(self, name: str) -> dict[str, Any]:
        """Get service details."""
        with self._client() as client:
            response = client.get(f"/services/{name}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def start_service(self, name: str) -> dict[str, Any]:
        """Start a service."""
        with self._client() as client:
            response = client.post(f"/services/{name}/start")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def stop_service(self, name: str, force: bool = False) -> dict[str, Any]:
        """Stop a service."""
        with self._client() as client:
            body = {"force": force} if force else None
            response = client.post(f"/services/{name}/stop", json=body)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def restart_service(self, name: str) -> dict[str, Any]:
        """Restart a service."""
        with self._client() as client:
            response = client.post(f"/services/{name}/restart")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def get_logs(
        self,
        name: str,
        tail: int | None = None,
        stream: str | None = None,
    ) -> dict[str, Any]:
        """Get service logs."""
        with self._client() as client:
            params: dict[str, str | int] = {}
            if tail is not None:
                params["tail"] = tail
            if stream is not None:
                params["stream"] = stream

            response = client.get(f"/services/{name}/logs", params=params)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def get_metrics(self, name: str | None = None) -> dict[str, Any]:
        """Get service metrics."""
        with self._client() as client:
            if name:
                response = client.get(f"/metrics/{name}")
            else:
                response = client.get("/metrics")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def is_available(self) -> bool:
        """Check if the daemon is available."""
        try:
            self.health()
            return True
        except (httpx.ConnectError, httpx.HTTPStatusError):
            return False
