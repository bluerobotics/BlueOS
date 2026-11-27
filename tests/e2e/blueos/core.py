import contextlib

from blueos.cable_guy import CableGuy
from blueos.http import request
from utils.retry import wait_until


class BlueOS:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.cable_guy = CableGuy(base_url)

    def wait_ready(self, timeout: float = 600) -> None:
        wait_until(self.version, timeout, errors=(OSError, RuntimeError), description=f"BlueOS at {self.base_url}")

    def version(self) -> dict[str, str]:
        version: dict[str, str] = request("GET", f"{self.base_url}/version-chooser/v1.0/version/current")
        return version

    def restart(self) -> None:
        """Restarts the core like the UI does, returns once it is back"""
        # version-chooser kills the core it runs in, so the answer may never arrive
        with contextlib.suppress(OSError):
            request("POST", f"{self.base_url}/version-chooser/v1.0/version/restart")

        def stopped() -> None:
            with contextlib.suppress(OSError, RuntimeError):
                self.version()
                raise AssertionError("BlueOS is still running")

        wait_until(stopped, 60, interval=0.5, errors=(AssertionError,), description="BlueOS stopping")
        self.wait_ready()
