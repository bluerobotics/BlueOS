import json
import urllib.request

from utils.retry import wait_until


class BlueOS:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def wait_ready(self, timeout: float = 600) -> None:
        wait_until(self.version, timeout, errors=(OSError,), description=f"BlueOS at {self.base_url}")

    def version(self) -> dict[str, str]:
        with urllib.request.urlopen(f"{self.base_url}/version-chooser/v1.0/version/current", timeout=10) as response:
            version: dict[str, str] = json.load(response)
        return version
