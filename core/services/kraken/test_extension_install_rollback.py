# isort: skip_file
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List, Optional
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
from loguru import logger  # noqa: E402
from extension.exceptions import ExtensionPullFailed  # noqa: E402
from extension.extension import Extension  # noqa: E402
from extension.models import ExtensionSource  # noqa: E402
from kraken import Kraken  # noqa: E402
from settings import ExtensionSettings  # noqa: E402

for module_name, module in _saved.items():
    if module is not None:
        sys.modules[module_name] = module
    else:
        sys.modules.pop(module_name, None)

pytestmark = pytest.mark.asyncio

DOCKER = "bluerobotics/blueos-ext"
DIGEST = "sha256:" + "a" * 64


def make_settings(tag: str, enabled: bool = True, permissions: str = "{}") -> ExtensionSettings:
    return ExtensionSettings(
        identifier="ext", name="Ext", docker=DOCKER, tag=tag, permissions=permissions, enabled=enabled,
        user_permissions="",
    )  # fmt: skip


def make_extension(tag: str, digest: Optional[str] = None, permissions: str = "{}") -> Extension:
    source = ExtensionSource(
        identifier="ext", tag=tag, name="Ext", docker=DOCKER, enabled=False, permissions=permissions
    )
    return Extension(source, digest)


class FakeDocker:
    """Docker client whose images are a ref -> Id map and whose pull replays the given lines."""

    def __init__(self, images: Dict[str, str], pull_lines: Optional[List[Dict[str, Any]]] = None) -> None:
        self.images = images
        self.pull_lines = pull_lines or []
        self.inspect_errors: Dict[str, int] = {}
        self.pulls = 0
        self.client = mock.AsyncMock()
        self.client.images.inspect.side_effect = self._inspect
        self.client.images.tag.side_effect = self._tag
        self.client.images.pull = self._pull

    async def _inspect(self, ref: str) -> Dict[str, str]:
        if ref in self.inspect_errors:
            raise DockerError(self.inspect_errors[ref], {"message": "boom"})  # type: ignore
        if ref not in self.images:
            raise DockerError(404, {"message": "no such image"})  # type: ignore
        return {"Id": self.images[ref]}

    async def _tag(self, source: str, repo: str, tag: Optional[str] = None) -> None:
        self.images[f"{repo}:{tag}" if tag else repo] = self.images[source]

    async def _pull(self, *_: Any, **__: Any) -> AsyncIterator[Dict[str, Any]]:
        self.pulls += 1
        for line in self.pull_lines:
            yield line


@pytest.fixture(name="env")
def fixture_env() -> Any:
    settings = SimpleNamespace(extensions=[])
    with (
        mock.patch.object(Extension, "_settings", settings),
        mock.patch.object(Extension, "_manager", mock.Mock()),
        mock.patch.object(Extension, "locked_entries", {}),
        mock.patch.object(Extension, "start_attempts", {}),
        mock.patch.object(Extension, "_clear_remaining_tags", mock.AsyncMock()) as clear,
    ):
        yield SimpleNamespace(settings=settings, clear=clear)


def use_docker(fake: FakeDocker, running: Optional[ExtensionSettings] = None) -> Any:
    ctx = mock.MagicMock()
    ctx.return_value.__aenter__ = mock.AsyncMock(return_value=fake.client)
    ctx.return_value.__aexit__ = mock.AsyncMock(return_value=False)

    async def disable_running() -> Optional[Extension]:
        if running is None:
            return None
        running.enabled = False
        return Extension(ExtensionSource.from_settings(running))

    stack = mock.patch("extension.extension.DockerCtx", ctx)
    stack2 = mock.patch.object(Extension, "_disable_running_extension", side_effect=disable_running)
    return (stack, stack2)


async def run_install(
    ext: Extension, fake: FakeDocker, running: Optional[ExtensionSettings] = None, pull: bool = True
) -> None:
    patch_ctx, patch_running = use_docker(fake, running)
    with patch_ctx, patch_running:
        async for _ in ext.install(pull=pull):
            pass


def tags(env: Any) -> Dict[str, bool]:
    return {ext.tag: ext.enabled for ext in env.settings.extensions}


OK_LINES = [{"status": "Pulling fs layer"}, {"status": "Digest: sha256:abc"}]


@pytest.mark.parametrize(
    "lines, message",
    [
        ([{"error": "denied"}], "denied"),
        ([{"errorDetail": {"message": "manifest unknown"}}], "manifest unknown"),
        ([{"errorDetail": None}, {"status": "Pulling fs layer"}], "image missing after pull"),
        ([{"status": "Pulling fs layer"}], "image missing after pull"),
    ],
)
async def test_pull_fails_on_in_band_error_or_missing_image(lines: List[Dict[str, Any]], message: str) -> None:
    fake = FakeDocker({}, lines)
    patch_ctx, _ = use_docker(fake)
    yielded = []
    with patch_ctx, pytest.raises(RuntimeError, match=message):
        async for line in make_extension("2")._pull_docker_image(None):
            yielded.append(line)
    assert len(yielded) == len(lines)


async def test_pull_accepts_a_stream_without_status_line_when_image_is_local() -> None:
    fake = FakeDocker({f"{DOCKER}:2": "id2"}, [{"status": "Pulling fs layer"}])
    patch_ctx, _ = use_docker(fake)
    with patch_ctx:
        async for _ in make_extension("2")._pull_docker_image(None):
            pass


async def test_digest_pull_retags_over_stale_tag() -> None:
    fake = FakeDocker({f"{DOCKER}:2": "old", f"{DOCKER}@{DIGEST}": "new"}, OK_LINES)
    patch_ctx, _ = use_docker(fake)
    with patch_ctx:
        async for _ in make_extension("2", DIGEST)._pull_docker_image(None):
            pass
    assert fake.images[f"{DOCKER}:2"] == "new"


async def test_failed_update_restores_running_tag(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1"}, [{"error": "not found"}])

    with pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("2"), fake, running)

    assert tags(env) == {"1": True}
    fake.client.images.delete.assert_not_awaited()
    env.clear.assert_not_awaited()


async def test_failed_pull_keeps_other_local_image(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1", f"{DOCKER}:2": "id2"}, [{"error": "offline"}])

    await run_install(make_extension("2"), fake, running)

    assert tags(env) == {"1": False, "2": True}
    env.clear.assert_not_awaited()


async def test_failed_pull_refuses_alias_of_running_image(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1", f"{DOCKER}:2": "id1"}, [{"error": "offline"}])

    with pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("2"), fake, running)

    assert tags(env) == {"1": True}


@pytest.mark.parametrize("status", [None, 500])
async def test_failed_pull_refuses_when_running_image_unknown(env: Any, status: Optional[int]) -> None:
    """None leaves the sibling absent (Docker answers 404), 500 makes the inspect itself fail."""
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:2": "id2"}, [{"error": "offline"}])
    if status:
        fake.inspect_errors[f"{DOCKER}:1"] = status

    with pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("2"), fake, running)

    assert tags(env) == {"1": True}


async def test_failed_pull_requires_exact_digest(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1", f"{DOCKER}:2": "stale"}, [{"error": "offline"}])

    with pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("2", DIGEST), fake, running)

    assert tags(env) == {"1": True}


async def test_same_tag_reinstall_keeps_new_permissions_when_image_is_local(env: Any) -> None:
    running = make_settings("1", permissions="{}")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1"}, [{"error": "offline"}])

    await run_install(make_extension("1", permissions='{"a": 1}'), fake, running)

    assert env.settings.extensions[0].permissions == '{"a": 1}'
    assert env.settings.extensions[0].enabled


@pytest.mark.parametrize("attempts, delay", [(1, 12), (9, 522), (10, 600), (20, 600)])
async def test_start_backoff_is_capped(attempts: int, delay: int) -> None:
    ext = make_settings("1")
    key = f"{ext.identifier}{ext.tag}"
    now = 10_000
    kraken = SimpleNamespace()
    with (
        mock.patch.object(Extension, "locked_entries", {}),
        mock.patch("kraken.time.monotonic", return_value=now),
    ):
        for elapsed, expected in ((delay, False), (delay + 1, True)):
            with mock.patch.object(Extension, "start_attempts", {key: (attempts, now - elapsed)}):
                assert Kraken._extension_start_try_valid(kraken, ext) is expected  # type: ignore


async def test_same_tag_failed_reinstall_restores_enabled_entry_even_if_enable_fails(env: Any) -> None:
    running = make_settings("1", permissions="{}")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1"}, [{"error": "offline"}])

    with mock.patch.object(Extension, "enable", side_effect=RuntimeError("boom")), pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("1", DIGEST, permissions='{"a": 1}'), fake, running)

    assert len(env.settings.extensions) == 1
    assert env.settings.extensions[0].permissions == "{}"
    assert env.settings.extensions[0].enabled


@pytest.mark.parametrize("save_fails, expected", [(False, "Rolled back"), (True, "Failed to roll back")])
async def test_rollback_only_reports_success_when_settings_were_restored(save_fails: bool, expected: str) -> None:
    messages: List[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="INFO")
    error = RuntimeError("disk full") if save_fails else None
    try:
        with mock.patch.object(Extension, "_save_settings", side_effect=error):
            await make_extension("2")._rollback_failed_install(None, None)
    finally:
        logger.remove(sink)

    assert any(expected in message for message in messages)
    assert any("Rolled back" in message for message in messages) is not save_fails


async def test_pull_reuses_the_callers_client() -> None:
    fake = FakeDocker({f"{DOCKER}:2": "id2"}, OK_LINES)
    with mock.patch("extension.extension.DockerCtx") as ctx:
        async for _ in make_extension("2")._pull_docker_image(None, fake.client):
            pass
    ctx.assert_not_called()


async def test_install_skips_pull_when_catalog_digest_image_is_local(env: Any) -> None:
    fake = FakeDocker({f"{DOCKER}@{DIGEST}": "new"}, [{"error": "offline"}])

    await run_install(make_extension("2", DIGEST), fake)

    assert fake.pulls == 0
    assert fake.images[f"{DOCKER}:2"] == "new"
    env.clear.assert_awaited_once()


async def test_install_without_digest_pulls_even_if_tag_is_local(env: Any) -> None:
    fake = FakeDocker({f"{DOCKER}:2": "id2"}, OK_LINES)

    await run_install(make_extension("2"), fake)

    assert fake.pulls == 1
    env.clear.assert_awaited_once()


@pytest.mark.parametrize(
    "lines, images, message",
    [
        ([{"error": "denied"}], {}, "denied"),
        (OK_LINES, {}, "image missing after pull"),
    ],
)
async def test_watchdog_start_fails_when_the_pull_fails(
    env: Any, lines: List[Dict[str, Any]], images: Dict[str, str], message: str
) -> None:
    env.settings.extensions = [make_settings("1")]
    fake = FakeDocker(images, lines)
    patch_ctx, _ = use_docker(fake)

    with patch_ctx, pytest.raises(ExtensionPullFailed, match=message):
        await make_extension("1").start()

    assert fake.pulls == 1
    fake.client.containers.create.assert_not_called()


async def test_rollback_resets_the_running_tags_start_backoff(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    Extension.mark_start_attempt(f"{running.identifier}{running.tag}")
    fake = FakeDocker({f"{DOCKER}:1": "id1"}, [{"error": "not found"}])

    with pytest.raises(ExtensionPullFailed):
        await run_install(make_extension("2"), fake, running)

    assert f"{running.identifier}{running.tag}" not in Extension.start_attempts


async def upload_finalize(env: Any, fake: FakeDocker, running: ExtensionSettings) -> Extension:
    temp = ExtensionSettings(
        identifier="", name="Ext", docker=DOCKER, tag="tmp", permissions="{}", enabled=False, user_permissions=""
    )  # fmt: skip
    env.settings.extensions = [running, temp]
    source = ExtensionSource(identifier="ext", tag="2", name="Ext", docker=DOCKER, enabled=False, permissions="{}")
    patch_ctx, _ = use_docker(fake)
    temp_source = ExtensionSource(identifier="", tag="tmp", name="Ext", docker=DOCKER, enabled=False, permissions="{}")
    with patch_ctx:
        return await Extension.finalize_temporary_extension(Extension(temp_source), source)


async def test_upload_of_the_running_image_under_a_new_tag_replaces_the_old_tag(env: Any) -> None:
    running = make_settings("1")
    fake = FakeDocker({f"{DOCKER}:1": "same", f"{DOCKER}:tmp": "same"}, [{"error": "manifest unknown"}])
    new_extension = await upload_finalize(env, fake, running)
    patch_ctx, patch_running = use_docker(fake, running)

    with patch_ctx, patch_running:
        async for _ in new_extension.install(pull=False):
            pass

    assert fake.pulls == 0
    assert tags(env) == {"1": False, "2": True}
    env.clear.assert_awaited_once()


async def test_install_without_pull_fails_before_touching_a_running_extension_when_image_is_missing(env: Any) -> None:
    running = make_settings("1")
    env.settings.extensions = [running]
    fake = FakeDocker({f"{DOCKER}:1": "id1"})

    with pytest.raises(ExtensionPullFailed, match="not available locally"):
        await run_install(make_extension("2"), fake, running, pull=False)

    assert tags(env) == {"1": True}
    assert fake.pulls == 0
    env.clear.assert_not_awaited()


async def test_failed_pull_after_upload_finalize_does_not_keep_the_new_entry(env: Any) -> None:
    running = make_settings("1")
    fake = FakeDocker({f"{DOCKER}:1": "same", f"{DOCKER}:tmp": "same"}, [{"error": "manifest unknown"}])
    new_extension = await upload_finalize(env, fake, running)

    with pytest.raises(ExtensionPullFailed):
        await run_install(new_extension, fake, running)

    assert tags(env) == {"1": True}
