import pytest
from blueos.core import BlueOS
from utils.retry import wait_until


@pytest.mark.usefixtures("network_without_internet")
def test_extension_store_is_empty_without_internet(blueos: BlueOS) -> None:
    manifests = wait_until(blueos.kraken.manifests, 120, errors=(OSError, RuntimeError), description="kraken manifests")
    assert manifests, "kraken has no manifest sources"
    assert not any(manifest["data"] for manifest in manifests), manifests
    # Installed extensions do not depend on the store
    blueos.kraken.extensions()
