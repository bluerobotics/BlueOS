import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from .. import general
from ..commands import HostFileError
from ..general import HostOs


@pytest.mark.parametrize(
    "os_release,expected_host_os",
    [
        ('PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"', HostOs.Bookworm),
        ('PRETTY_NAME="Raspbian GNU/Linux 11 (bullseye)"', HostOs.Bullseye),
        ('PRETTY_NAME="Ubuntu 22.04.3 LTS"', HostOs.Other),
    ],
)
def test_get_host_os(os_release: str, expected_host_os: HostOs, monkeypatch: pytest.MonkeyPatch) -> None:
    general.get_host_os.cache_clear()
    monkeypatch.setattr(general, "load_file", lambda _: os_release)
    assert general.get_host_os() == expected_host_os
    general.get_host_os.cache_clear()


def test_get_host_os_returns_other_when_load_file_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    general.get_host_os.cache_clear()

    def raise_host_file_error(_file_name: str) -> str:
        raise HostFileError("Failed to read /etc/os-release")

    monkeypatch.setattr(general, "load_file", raise_host_file_error)
    assert general.get_host_os() == HostOs.Other
    general.get_host_os.cache_clear()


def test_blueos_version(monkeypatch: pytest.MonkeyPatch) -> None:
    general.blueos_version.cache_clear()
    monkeypatch.setenv("GIT_DESCRIBE_TAGS", "1.5.0-10-gabcdef12")
    assert general.blueos_version() == "1.5.0-10-gabcdef12"
    general.blueos_version.cache_clear()
    monkeypatch.delenv("GIT_DESCRIBE_TAGS")
    assert general.blueos_version() == "null"
    general.blueos_version.cache_clear()


def test_file_is_open(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")
    assert general.file_is_open(target) is False
    with open(target, "r", encoding="utf-8"):
        assert general.file_is_open(target) is True


def test_file_is_open_when_lsof_fails_to_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def raise_oserror(*_args: object, **_kwargs: object) -> None:
        raise OSError("lsof missing")

    monkeypatch.setattr(subprocess, "run", raise_oserror)
    assert general.file_is_open(tmp_path / "target.txt") is True


def test_open_files_under_reports_open_file(tmp_path: Path) -> None:
    held = tmp_path / "in-use.txt"
    held.write_text("in use", encoding="utf-8")
    closed = tmp_path / "closed.txt"
    closed.write_text("closed", encoding="utf-8")

    with open(held, "r", encoding="utf-8"):
        open_files = general.open_files_under(tmp_path)

    assert open_files is not None
    assert held.resolve() in open_files
    assert closed.resolve() not in open_files


def test_open_files_under_when_lsof_fails_to_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def raise_oserror(*_args: object, **_kwargs: object) -> None:
        raise OSError("lsof missing")

    monkeypatch.setattr(subprocess, "run", raise_oserror)
    assert general.open_files_under(tmp_path) is None


def test_open_files_under_when_lsof_reports_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def failing_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="lsof: status error")

    monkeypatch.setattr(subprocess, "run", failing_run)
    assert general.open_files_under(tmp_path) is None


def test_delete_everything(tmp_path: Path) -> None:
    root = tmp_path / "data"
    keep_dir = root / "keep"
    doomed_dir = root / "doomed"
    keep_dir.mkdir(parents=True)
    doomed_dir.mkdir()
    kept_file = keep_dir / "kept.txt"
    kept_file.write_text("kept", encoding="utf-8")
    kept_top_level = root / "kept-top-level.txt"
    kept_top_level.write_text("kept", encoding="utf-8")
    (root / "doomed-top-level.txt").write_text("doomed", encoding="utf-8")
    (doomed_dir / "doomed-nested.txt").write_text("doomed", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "untouchable.txt"
    outside_file.write_text("untouchable", encoding="utf-8")
    (root / "link-to-outside").symlink_to(outside)

    general.delete_everything(root, ignore=[keep_dir, kept_top_level])

    assert kept_file.exists()
    assert kept_top_level.exists()
    assert not (root / "doomed-top-level.txt").exists()
    assert not (doomed_dir / "doomed-nested.txt").exists()
    # Symlinked directories are not followed
    assert outside_file.exists()


def test_delete_everything_single_file(tmp_path: Path) -> None:
    target = tmp_path / "single.txt"
    target.write_text("data", encoding="utf-8")

    general.delete_everything(target, ignore=[target])
    assert target.exists()

    general.delete_everything(target)
    assert not target.exists()


def test_delete_everything_keeps_open_files_with_one_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "data"
    nested = root / "nested"
    nested.mkdir(parents=True)
    for index in range(10):
        (root / f"file-{index}.txt").write_text("data", encoding="utf-8")
        (nested / f"file-{index}.txt").write_text("data", encoding="utf-8")
    held = root / "in-use.txt"
    held.write_text("in use", encoding="utf-8")

    spawns = 0
    original = subprocess.run

    def counting_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawns
        spawns += 1
        return original(*args, **kwargs)  # pylint: disable=subprocess-run-check

    monkeypatch.setattr(subprocess, "run", counting_run)

    with open(held, "r", encoding="utf-8"):
        general.delete_everything(root)

    assert held.exists()
    assert not (root / "file-0.txt").exists()
    assert not (nested / "file-0.txt").exists()
    # A single lsof pass covers the whole tree, spawning one process per file is what makes deletion time out
    assert spawns == 1


def test_delete_everything_on_open_file_keeps_it_quietly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "service.log"
    target.write_text("data", encoding="utf-8")

    spawns = 0
    original = subprocess.run

    def counting_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawns
        spawns += 1
        return original(*args, **kwargs)  # pylint: disable=subprocess-run-check

    monkeypatch.setattr(subprocess, "run", counting_run)

    with open(target, "r", encoding="utf-8"):
        general.delete_everything(target)

    assert target.exists()
    # lsof cannot search a single file, and log_zipper deletes file by file: only the open check may run
    assert spawns == 1


def test_delete_everything_through_symlinked_folder(tmp_path: Path) -> None:
    # /shortcuts/ardupilot_logs/logs is a symlink to the folder ArduPilot writes to
    real = tmp_path / "ardupilot-manager" / "logs"
    real.mkdir(parents=True)
    held = real / "00000042.BIN"
    held.write_text("being written", encoding="utf-8")
    doomed = real / "00000041.BIN"
    doomed.write_text("old", encoding="utf-8")
    shortcut = tmp_path / "ardupilot_logs"
    shortcut.symlink_to(real)

    with open(held, "r", encoding="utf-8"):
        general.delete_everything(shortcut)

    assert held.exists()
    assert not doomed.exists()


@pytest.mark.asyncio
async def test_delete_everything_stream(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    nested = root / "nested"
    nested.mkdir(parents=True)
    small = root / "small.txt"
    small.write_text("12345", encoding="utf-8")
    nested_file = nested / "inner.txt"
    nested_file.write_text("abc", encoding="utf-8")
    rotated_log = root / "rotated.gz"
    rotated_log.write_text("gz", encoding="utf-8")

    infos = [info async for info in general.delete_everything_stream(root)]

    assert {info["path"] for info in infos} == {str(small), str(nested_file), str(rotated_log)}
    assert all(info["success"] for info in infos)
    assert all(info["type"] == "file" for info in infos)
    sizes = {info["path"]: info["size"] for info in infos}
    assert sizes[str(small)] == 5
    assert not small.exists()
    assert not nested_file.exists()
    assert not rotated_log.exists()


@pytest.mark.asyncio
async def test_delete_everything_stream_single_file(tmp_path: Path) -> None:
    target = tmp_path / "single.txt"
    target.write_text("data", encoding="utf-8")

    infos = [info async for info in general.delete_everything_stream(target)]

    assert infos == [{"path": str(target), "size": 4, "type": "file", "success": True}]
    assert not target.exists()


@pytest.mark.asyncio
async def test_delete_everything_stream_keeps_open_files(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    root.mkdir()
    held = root / "in-use.txt"
    held.write_text("in use", encoding="utf-8")
    doomed = root / "doomed.txt"
    doomed.write_text("doomed", encoding="utf-8")

    with open(held, "r", encoding="utf-8"):
        infos = [info async for info in general.delete_everything_stream(root)]

    assert {info["path"] for info in infos} == {str(doomed)}
    assert held.exists()
    assert not doomed.exists()


@pytest.mark.asyncio
async def test_delete_everything_stream_checks_open_files_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "logs"
    nested = root / "nested"
    nested.mkdir(parents=True)
    for index in range(10):
        (root / f"file-{index}.txt").write_text("data", encoding="utf-8")
        (nested / f"file-{index}.txt").write_text("data", encoding="utf-8")

    spawns = 0
    original = subprocess.run

    def counting_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawns
        spawns += 1
        return original(*args, **kwargs)  # pylint: disable=subprocess-run-check

    monkeypatch.setattr(subprocess, "run", counting_run)
    infos = [info async for info in general.delete_everything_stream(root)]

    assert len(infos) == 20
    # A single lsof pass covers the whole tree, spawning one process per file is what makes deletion time out
    assert spawns == 1


@pytest.mark.asyncio
async def test_delete_everything_stream_falls_back_when_lsof_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "logs"
    root.mkdir()
    held = root / "in-use.txt"
    held.write_text("in use", encoding="utf-8")
    doomed = root / "doomed.txt"
    doomed.write_text("doomed", encoding="utf-8")

    def failed_snapshot(_path: Path) -> None:
        return None

    monkeypatch.setattr(general, "open_files_under", failed_snapshot)

    with open(held, "r", encoding="utf-8"):
        infos = [info async for info in general.delete_everything_stream(root)]

    assert {info["path"] for info in infos} == {str(doomed)}
    assert held.exists()
    assert not doomed.exists()


def test_local_unique_identifier_reads_existing(fs: FakeFilesystem) -> None:
    general.local_unique_identifier.cache_clear()
    existing = uuid.uuid4().hex
    fs.create_file("/etc/blueos/uuid", contents=existing)
    assert general.local_unique_identifier() == existing
    general.local_unique_identifier.cache_clear()


def test_local_unique_identifier_regenerates_invalid(fs: FakeFilesystem) -> None:
    general.local_unique_identifier.cache_clear()
    fs.create_file("/etc/blueos/uuid", contents="not-a-uuid")
    result = general.local_unique_identifier()
    assert uuid.UUID(result, version=4)
    assert Path("/etc/blueos/uuid").read_text(encoding="utf-8") == result
    general.local_unique_identifier.cache_clear()


def test_local_unique_identifier_unwritable(fs: FakeFilesystem) -> None:
    general.local_unique_identifier.cache_clear()
    # /etc exists but /etc/blueos does not, so both reading and persisting fail
    fs.create_dir("/etc")
    assert general.local_unique_identifier() == "00000000000040000000000000000000"
    general.local_unique_identifier.cache_clear()


def test_local_hardware_identifier_reads_existing(fs: FakeFilesystem) -> None:
    general.local_hardware_identifier.cache_clear()
    hardware_uuid = str(uuid.uuid4())
    fs.create_file("/etc/blueos/hardware-uuid", contents=hardware_uuid)
    assert general.local_hardware_identifier() == hardware_uuid
    general.local_hardware_identifier.cache_clear()


def test_local_hardware_identifier_missing_or_invalid(fs: FakeFilesystem) -> None:
    general.local_hardware_identifier.cache_clear()
    fs.create_dir("/etc")
    assert general.local_hardware_identifier() == "00000000000030000000000000000000"
    general.local_hardware_identifier.cache_clear()
    fs.create_file("/etc/blueos/hardware-uuid", contents="garbage")
    assert general.local_hardware_identifier() == "00000000000030000000000000000000"
    general.local_hardware_identifier.cache_clear()


def test_device_id_from_serial_number(fs: FakeFilesystem) -> None:
    fs.create_file("/sys/firmware/devicetree/base/serial-number", contents="10000000abcdef01")
    assert general.device_id() == "10000000abcdef01"


def test_device_id_falls_back_to_machine_id(fs: FakeFilesystem) -> None:
    fs.create_file("/etc/machine-id", contents="abc123def456\n")
    assert general.device_id() == "abc123def456"


def test_device_id_raises_without_sources(fs: FakeFilesystem) -> None:
    fs.create_dir("/etc")
    with pytest.raises(ValueError, match="Could not get device id"):
        general.device_id()


def test_is_running_as_root_matches_euid() -> None:
    assert general.is_running_as_root() == (os.geteuid() == 0)


def test_available_disk_space_mb() -> None:
    space = general.available_disk_space_mb()
    assert isinstance(space, float)
    assert space > 0
