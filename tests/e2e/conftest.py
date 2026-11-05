import logging
from collections.abc import Iterator

import pytest
from blueos.core import BlueOS
from targets.hil.target import HilTarget
from targets.sil.target import SilTarget
from targets.target import Target

logger = logging.getLogger(__name__)


@pytest.fixture(
    name="target", scope="session", params=[SilTarget, HilTarget], ids=lambda target_class: target_class.name
)
def target_fixture(request: pytest.FixtureRequest) -> Iterator[Target]:
    target = request.param()
    logger.info("setting up %s target...", target.name)
    try:
        target.up()
    except NotImplementedError:
        pytest.skip(f"{target.name} target not implemented")
    except BaseException:
        target.down()
        raise
    yield target
    target.down()


@pytest.fixture(name="blueos", scope="session")
def blueos_fixture(target: Target) -> BlueOS:
    blueos = BlueOS(target.base_url)
    blueos.wait_ready()
    return blueos
