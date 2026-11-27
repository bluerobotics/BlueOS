import pytest
from blueos.core import BlueOS


@pytest.fixture(autouse=True)
def ardupilot_ready(blueos: BlueOS) -> None:
    blueos.ardupilot.wait_ready()
