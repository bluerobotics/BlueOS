from blueos.core import BlueOS
from images import CORE


def test_blueos_runs_expected_image(blueos: BlueOS) -> None:
    repository, _, tag = CORE.rpartition(":")
    version = blueos.version()
    assert (version["repository"], version["tag"]) == (repository, tag)
