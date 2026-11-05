import pytest
from features.wifi import WifiAccessPoints, WifiScanner
from targets.target import Target


@pytest.fixture
def access_points(target: Target) -> WifiAccessPoints:
    try:
        return target.feature(WifiAccessPoints)
    except NotImplementedError as error:
        pytest.skip(str(error))


@pytest.fixture
def scanner(target: Target) -> WifiScanner:
    try:
        return target.feature(WifiScanner)
    except NotImplementedError as error:
        pytest.skip(str(error))
