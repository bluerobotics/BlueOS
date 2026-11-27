from collections.abc import Iterator

import pytest
from blueos.core import BlueOS
from features.network import ClientPc, Router
from targets.target import Target


@pytest.fixture(name="client_pc", scope="session")
def client_pc_fixture(target: Target) -> ClientPc:
    return target.feature(ClientPc)


@pytest.fixture
def network_without_dhcp_server(router: Router, blueos: BlueOS) -> Iterator[None]:
    try:
        with router.without_dhcp_server():
            blueos.restart()
            yield
    finally:
        blueos.restart()
