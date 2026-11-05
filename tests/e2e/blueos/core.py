from blueos.http import request
from utils.retry import wait_until


class BlueOS:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def wait_ready(self, timeout: float = 600) -> None:
        wait_until(self.version, timeout, errors=(OSError, RuntimeError), description=f"BlueOS at {self.base_url}")

    def version(self) -> dict[str, str]:
        version: dict[str, str] = request("GET", f"{self.base_url}/version-chooser/v1.0/version/current")
        return version
