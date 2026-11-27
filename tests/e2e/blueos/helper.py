from typing import Any

from blueos.http import request


class Helper:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/helper/v1.0"

    def internet_access(self) -> dict[str, dict[str, Any]]:
        """The sites BlueOS checks, with whether each one is online"""
        result: dict[str, dict[str, Any]] = request("GET", f"{self.url}/check_internet_access")
        return result

    def web_services(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = request("GET", f"{self.url}/web_services")
        return result
