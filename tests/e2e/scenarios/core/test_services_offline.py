from blueos.core import BlueOS
from utils.retry import wait_until


def test_blueos_runs_the_same_services_without_internet(network_without_internet: set[int], blueos: BlueOS) -> None:
    def all_running() -> None:
        missing = network_without_internet - {service["port"] for service in blueos.helper.web_services()}
        assert not missing, f"services on ports {sorted(missing)} did not start without internet"

    wait_until(all_running, 300, errors=(AssertionError,), description="BlueOS services running offline")
