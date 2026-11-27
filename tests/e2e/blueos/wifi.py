import urllib.parse
from typing import Any

from blueos.http import request
from utils.retry import wait_until


class Wifi:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/wifi-manager/v1.0"

    def wait_ready(self, timeout: float = 300) -> None:
        wait_until(self.status, timeout, errors=(OSError, RuntimeError), description="wifi-manager")

    def scan(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", "/scan")
        return result

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = self._request("GET", "/status")
        return result

    def connect(self, ssid: str, password: str) -> None:
        self._request("POST", "/connect", {"ssid": ssid, "password": password})

    def saved(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", "/saved")
        return result

    def hotspot_enabled(self) -> bool:
        return bool(self._request("GET", "/hotspot"))

    def enable_hotspot(self) -> bool:
        return bool(self._request("POST", "/hotspot?enable=true"))

    def hotspot_credentials(self) -> dict[str, str]:
        result: dict[str, str] = self._request("GET", "/hotspot_credentials")
        return result

    def remove(self, ssid: str) -> None:
        self._request("POST", f"/remove?{urllib.parse.urlencode({'ssid': ssid})}")

    def _request(self, method: str, path: str, body: dict[str, str] | None = None) -> Any:
        return request(method, f"{self.url}{path}", body)
