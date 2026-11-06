import sys
from pathlib import Path
from typing import Any, List
from unittest import mock

import pytest

_KRAKEN_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _KRAKEN_DIR)
# Root pytest also collects the other services, whose top-level `config` and
# `settings` modules would otherwise be the ones imported here.
_saved = {module_name: sys.modules.get(module_name) for module_name in ("config", "settings", "utils")}
for module_name in _saved:
    sys.modules.pop(module_name, None)

from extension.extension import Extension  # noqa: E402
from extension.models import ExtensionSource  # noqa: E402

for module_name, module in _saved.items():
    if module is not None:
        sys.modules[module_name] = module
    else:
        sys.modules.pop(module_name, None)

pytestmark = pytest.mark.asyncio

DIGEST = "sha256:" + "1" * 64


def make_source(docker: str = "bluerobotics/blueos-ping-viewer-next", tag: str = "1.0.0") -> ExtensionSource:
    return ExtensionSource(
        identifier="blueos-ping-viewer-next",
        tag=tag,
        name="Ping Viewer",
        docker=docker,
        enabled=False,
        permissions="{}",
    )


async def progress() -> Any:
    yield {"status": "Pulling"}


def pull_client() -> Any:
    """A DockerCtx stand-in that records the pull request instead of making it."""
    client = mock.MagicMock()
    client.images.pull = mock.MagicMock(side_effect=lambda *_args, **_kwargs: progress())
    client.images.tag = mock.AsyncMock()

    context = mock.MagicMock()
    context.__aenter__ = mock.AsyncMock(return_value=client)
    context.__aexit__ = mock.AsyncMock(return_value=None)
    return context, client


async def drain(extension: Extension) -> List[bytes]:
    return [line async for line in extension._pull_docker_image(None)]


async def test_pull_sends_a_single_reference() -> None:
    """`repo` and `tag` alongside a tagged `fromImage` ask Podman for `repo:tag:tag`."""
    context, client = pull_client()
    with mock.patch("extension.extension.DockerCtx", return_value=context):
        await drain(Extension(make_source()))

    assert client.images.pull.call_args.args == ("bluerobotics/blueos-ping-viewer-next:1.0.0",)
    assert client.images.pull.call_args.kwargs == {"auth": None, "stream": True}


async def test_pull_pins_a_digest_in_the_reference() -> None:
    context, client = pull_client()
    with mock.patch("extension.extension.DockerCtx", return_value=context):
        await drain(Extension(make_source(), digest=DIGEST))

    assert client.images.pull.call_args.args == (f"bluerobotics/blueos-ping-viewer-next:1.0.0@{DIGEST}",)


async def test_digest_pull_is_tagged_for_the_settings_entry() -> None:
    """A digest pull leaves the image untagged, and the settings name the tag."""
    context, client = pull_client()
    with mock.patch("extension.extension.DockerCtx", return_value=context):
        await drain(Extension(make_source(), digest=DIGEST))

    client.images.tag.assert_awaited_once_with(
        f"bluerobotics/blueos-ping-viewer-next:1.0.0@{DIGEST}",
        "bluerobotics/blueos-ping-viewer-next",
        tag="1.0.0",
    )


async def test_tagged_pull_is_not_tagged_again() -> None:
    context, client = pull_client()
    with mock.patch("extension.extension.DockerCtx", return_value=context):
        await drain(Extension(make_source()))

    client.images.tag.assert_not_awaited()
