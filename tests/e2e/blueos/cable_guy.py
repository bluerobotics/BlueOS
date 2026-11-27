from typing import Any

from blueos.http import request


class CableGuy:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/cable-guy/v1.0"

    def dhcp_leases(self, interface: str) -> list[dict[str, Any]]:
        leases: dict[str, list[dict[str, Any]]] = request("GET", f"{self.url}/dhcp/leases/{interface}")
        return leases.get(interface, [])
