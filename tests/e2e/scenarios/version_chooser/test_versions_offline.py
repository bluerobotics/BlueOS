import pytest
from blueos.core import BlueOS
from images import CORE


@pytest.mark.usefixtures("network_without_internet")
def test_version_list_falls_back_to_local_versions_without_internet(blueos: BlueOS) -> None:
    repository, _, tag = CORE.rpartition(":")
    versions = blueos.available_versions(repository)
    assert versions["error"], versions
    assert not versions["remote"], versions
    assert tag in [version["tag"] for version in versions["local"]], versions
