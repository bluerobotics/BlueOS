from collections.abc import Iterator

import pytest
from blueos.core import BlueOS
from features.network import Router
from targets.target import Target


@pytest.fixture(name="router", scope="session")
def router_fixture(target: Target) -> Router:
    return target.feature(Router)


@pytest.fixture(scope="module")
def network_without_internet(router: Router, blueos: BlueOS) -> Iterator[set[int]]:
    """Yields the ports of the services BlueOS ran before going offline"""
    online = {service["port"] for service in blueos.helper.web_services()}
    try:
        with router.without_internet():
            blueos.restart()
            yield online
    finally:
        # Services that started offline may not retry what they missed
        blueos.restart()
