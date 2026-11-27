from typing import Any

from blueos.http import request


class Kraken:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/kraken/v2.0"

    def manifests(self) -> list[dict[str, Any]]:
        """The extension store, fetched from the internet"""
        result: list[dict[str, Any]] = request("GET", f"{self.url}/manifest/")
        return result

    def extensions(self) -> list[dict[str, Any]]:
        """The installed extensions"""
        result: list[dict[str, Any]] = request("GET", f"{self.url}/extension/")
        return result
