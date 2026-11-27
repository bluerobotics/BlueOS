import pytest
from features.network import Router
from targets.target import Target


@pytest.fixture(name="router", scope="session")
def router_fixture(target: Target) -> Router:
    return target.feature(Router)

