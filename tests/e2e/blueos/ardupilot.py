from typing import Any

from blueos.http import request
from utils.retry import wait_until


class Ardupilot:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/ardupilot-manager/v1.0"

    def wait_ready(self, timeout: float = 300) -> None:
        wait_until(self.available_boards, timeout, errors=(OSError, RuntimeError), description="ardupilot-manager")

    def available_boards(self) -> list[dict[str, Any]]:
        boards: list[dict[str, Any]] = request("GET", f"{self.url}/available_boards")
        return boards

    def board(self) -> dict[str, Any] | None:
        board: dict[str, Any] | None = request("GET", f"{self.url}/board")
        return board

    def set_board(self, board: dict[str, Any]) -> None:
        request("POST", f"{self.url}/board", board, timeout=300)

    def stop(self) -> None:
        request("POST", f"{self.url}/stop")

    def vehicle_type(self) -> str:
        vehicle_type: str = request("GET", f"{self.url}/vehicle_type")
        return vehicle_type
