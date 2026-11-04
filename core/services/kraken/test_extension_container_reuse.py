import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest

_KRAKEN_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _KRAKEN_DIR)
# Root pytest also collects the other services, whose top-level `config` and
# `settings` modules would otherwise be the ones imported here.
_saved = {module_name: sys.modules.get(module_name) for module_name in ("config", "settings", "utils")}
for module_name in _saved:
    sys.modules.pop(module_name, None)

from aiodocker.exceptions import DockerError  # noqa: E402
from extension.extension import CONFIG_FINGERPRINT_LABEL, Extension  # noqa: E402

for module_name, module in _saved.items():
    if module is not None:
        sys.modules[module_name] = module
    else:
        sys.modules.pop(module_name, None)

pytestmark = pytest.mark.asyncio


def make_config(**overrides: Any) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "Image": "bluerobotics/blueos-ping-viewer-next:1.0.0",
        "HostConfig": {"NetworkMode": "host"},
    }
    config.update(overrides)
    return config


def make_container(raw: Dict[str, Any], container_id: str = "container-id") -> mock.AsyncMock:
    """A stand-in for aiodocker's DockerContainer, faithful to what kraken reads."""
    container = mock.AsyncMock()
    container.id = container_id
    container.__getitem__ = mock.Mock(side_effect=lambda key: raw[key])
    container.show.return_value = raw
    container.delete = mock.AsyncMock()
    container.start = mock.AsyncMock()
    container.stop = mock.AsyncMock()
    return container


def inspected(state: str, labels: Optional[Dict[str, str]] = None, image: str = "repo:tag") -> Dict[str, Any]:
    """The subset of a `GET /containers/{id}/json` body that the reuse logic reads."""
    return {
        "Id": "container-id",
        "Image": "sha256:" + "0" * 64,
        "Created": "2026-01-01T00:00:00Z",
        "Config": {"Image": image, "Labels": labels or {}},
        "State": {"Status": state, "Running": state == "running"},
    }


def client_returning(container: Any) -> Any:
    client = mock.AsyncMock()
    client.containers.get.return_value = container
    created = mock.AsyncMock()
    client.containers.create.return_value = created
    return client


async def test_creates_container_when_absent() -> None:
    client = client_returning(None)
    client.containers.get.side_effect = DockerError(404, {"message": "no such container"})

    config = make_config()
    result = await Extension._start_or_create(client, "extension-name", config, "sha256:abc")

    assert result is client.containers.create.return_value
    client.containers.create.assert_awaited_once()
    assert client.containers.create.await_args.kwargs["name"] == "extension-name"


async def test_reuses_container_when_configuration_matches() -> None:
    """An unchanged config must not tear the container down."""
    config = make_config()
    image_id = "sha256:abc"
    fingerprint = Extension._config_fingerprint(config, image_id)

    container = make_container(inspected("running", {CONFIG_FINGERPRINT_LABEL: fingerprint}))
    client = client_returning(container)

    result = await Extension._start_or_create(client, "extension-name", config, image_id)

    assert result is container
    client.containers.create.assert_not_awaited()
    container.delete.assert_not_awaited()
    container.stop.assert_not_awaited()


async def test_reuses_stopped_container_without_recreating_it() -> None:
    config = make_config()
    image_id = "sha256:abc"
    fingerprint = Extension._config_fingerprint(config, image_id)

    container = make_container(inspected("exited", {CONFIG_FINGERPRINT_LABEL: fingerprint}))
    client = client_returning(container)

    result = await Extension._start_or_create(client, "extension-name", config, image_id)

    assert result is container
    client.containers.create.assert_not_awaited()
    container.delete.assert_not_awaited()


async def test_replaces_container_when_configuration_changes() -> None:
    config = make_config(HostConfig={"NetworkMode": "host", "Privileged": True})
    container = make_container(inspected("running", {CONFIG_FINGERPRINT_LABEL: "stale"}))
    client = client_returning(container)

    result = await Extension._start_or_create(client, "extension-name", config, "sha256:abc")

    container.stop.assert_awaited_once()
    container.delete.assert_awaited_once()
    assert result is client.containers.create.return_value


async def test_replaces_container_when_image_changes() -> None:
    """A re-pulled tag must not keep running the old image."""
    config = make_config()
    container = make_container(
        inspected("exited", {CONFIG_FINGERPRINT_LABEL: Extension._config_fingerprint(config, "sha256:old")})
    )
    client = client_returning(container)

    result = await Extension._start_or_create(client, "extension-name", config, "sha256:new")

    container.delete.assert_awaited_once()
    assert result is client.containers.create.return_value


async def test_replaces_container_created_before_fingerprints() -> None:
    """Containers from older versions carry no label, so they migrate once."""
    config = make_config()
    container = make_container(inspected("exited", {}))
    client = client_returning(container)

    await Extension._start_or_create(client, "extension-name", config, "sha256:abc")

    container.delete.assert_awaited_once()
    client.containers.create.assert_awaited_once()


async def test_propagates_unexpected_get_errors() -> None:
    """A daemon that is down must not be mistaken for a missing container."""
    client = client_returning(None)
    client.containers.get.side_effect = DockerError(500, {"message": "daemon unavailable"})

    with pytest.raises(DockerError):
        await Extension._start_or_create(client, "extension-name", make_config(), "sha256:abc")

    client.containers.create.assert_not_awaited()


async def test_fingerprint_is_stable_across_calls() -> None:
    """Regression: hashing the label it adds made every start look like a change."""
    config = make_config()
    first = Extension._config_fingerprint(config, "sha256:abc")
    config.setdefault("Labels", {})[CONFIG_FINGERPRINT_LABEL] = first
    second = Extension._config_fingerprint(config, "sha256:abc")

    assert first == second


async def test_fingerprint_ignores_the_label_it_adds() -> None:
    config = make_config()
    labelled = make_config(Labels={CONFIG_FINGERPRINT_LABEL: "irrelevant"})

    assert Extension._config_fingerprint(config, "sha256:abc") == Extension._config_fingerprint(labelled, "sha256:abc")


async def test_fingerprint_tracks_extension_labels() -> None:
    """Labels an extension declares are part of its configuration."""
    plain = make_config()
    tagged = make_config(Labels={"maintainer": "blueos"})

    assert Extension._config_fingerprint(plain, "sha256:abc") != Extension._config_fingerprint(tagged, "sha256:abc")


async def test_fingerprint_tracks_image_id() -> None:
    config = make_config()

    assert Extension._config_fingerprint(config, "sha256:one") != Extension._config_fingerprint(config, "sha256:two")


async def test_fingerprint_survives_serialisation() -> None:
    """Configurations arrive as parsed JSON, so they must be hashable as such."""
    config = json.loads(json.dumps(make_config(HostConfig={"Binds": ["/a:/b:rw"]})))

    with mock.patch.dict("os.environ", {"MAV_SYSTEM_ID": "1"}):
        assert Extension._config_fingerprint(config, "sha256:abc")


async def test_reuse_preserves_the_fingerprint_label_for_the_next_start() -> None:
    """The label written on create is what a later start compares against."""
    config: Dict[str, Any] = make_config()
    image_id = "sha256:abc"
    created_raw: List[Dict[str, Any]] = []

    async def create(cfg: Dict[str, Any], name: str) -> Any:  # pylint: disable=unused-argument
        created_raw.append(json.loads(json.dumps(cfg)))
        return make_container(inspected("created", cfg["Labels"]))

    client = mock.AsyncMock()
    client.containers.get.side_effect = DockerError(404, {"message": "no such container"})
    client.containers.create.side_effect = create

    await Extension._start_or_create(client, "extension-name", config, image_id)
    stored = created_raw[0]["Labels"][CONFIG_FINGERPRINT_LABEL]

    reused = make_container(inspected("exited", {CONFIG_FINGERPRINT_LABEL: stored}))
    second_client = client_returning(reused)
    result = await Extension._start_or_create(second_client, "extension-name", make_config(), image_id)

    assert result is reused
    second_client.containers.create.assert_not_awaited()
