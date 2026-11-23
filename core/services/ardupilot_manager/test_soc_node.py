import asyncio
import pathlib
import shutil

import pytest
from autopilot_manager import alias_soc_node, soc_node_needs_alias


def test_soc_alias_is_only_added_when_the_plain_node_is_missing(tmp_path: pathlib.Path) -> None:
    assert not soc_node_needs_alias(tmp_path)

    (tmp_path / "soc@107c000000").mkdir()
    assert soc_node_needs_alias(tmp_path)

    (tmp_path / "soc").mkdir()
    assert not soc_node_needs_alias(tmp_path)


class FakeProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode


def fake_copy(monkeypatch: pytest.MonkeyPatch, returncode: int) -> None:
    async def create_subprocess_exec(*_args: object) -> FakeProcess:
        return FakeProcess(returncode)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess_exec)


def test_soc_alias_wraps_the_command_in_a_private_mount(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    device_tree = tmp_path / "device-tree"
    (device_tree / "soc@107c000000").mkdir(parents=True)
    copy = tmp_path / "copy"
    copy.mkdir()
    fake_copy(monkeypatch, 0)
    monkeypatch.setattr(shutil, "rmtree", lambda *_args, **_kwargs: None)

    command_line = asyncio.run(alias_soc_node("ardupilot -A", device_tree, copy))

    assert command_line.startswith("unshare -m sh -c ")
    assert "exec ardupilot -A" in command_line
    assert (copy / "soc").readlink() == pathlib.Path("soc@107c000000")


def test_soc_alias_failing_to_copy_runs_without_it(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    device_tree = tmp_path / "device-tree"
    (device_tree / "soc@107c000000").mkdir(parents=True)
    fake_copy(monkeypatch, 1)

    assert asyncio.run(alias_soc_node("ardupilot -A", device_tree, tmp_path / "copy")) == "ardupilot -A"
