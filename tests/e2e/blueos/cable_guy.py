from typing import Any

from blueos.http import request


class CableGuy:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/cable-guy/v1.0"

    def ethernet(self, interface: str) -> dict[str, Any]:
        interfaces: list[dict[str, Any]] = request("GET", f"{self.url}/ethernet")
        return next(item for item in interfaces if item["name"] == interface)

    def dhcp_leases(self, interface: str) -> list[dict[str, Any]]:
        leases: dict[str, list[dict[str, Any]]] = request("GET", f"{self.url}/dhcp/leases/{interface}")
        return leases.get(interface, [])
