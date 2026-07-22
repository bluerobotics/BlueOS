import os
import subprocess
import uuid
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from .. import general
from ..general import CpuType, HostOs, get_cpu_type

CPUINFO_TEMPLATE = """processor	: 0
BogoMIPS	: 108.00
Features	: fp asimd evtstrm crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8

Hardware	: BCM2835
Revision	: d03141
Serial		: 10000000abcdef01
Model		: {model}
"""


@pytest.mark.parametrize(
    "model,expected_cpu_type",
    [
        ("Raspberry Pi 3 Model B Rev 1.2", CpuType.PI3),
        ("Raspberry Pi 4 Model B Rev 1.4", CpuType.PI4),
        ("Raspberry Pi 5 Model B Rev 1.0", CpuType.PI5),
        ("Raspberry Pi Compute Module 4 Rev 1.1", CpuType.PI4),
        ("Raspberry Pi Compute Module 5 Rev 1.0", CpuType.PI5),
        ("Some Other Board", CpuType.Other),
    ],
)
def test_get_cpu_type(model: str, expected_cpu_type: CpuType) -> None:
    cpuinfo = CPUINFO_TEMPLATE.format(model=model)
    get_cpu_type.cache_clear()
    with patch("builtins.open", mock_open(read_data=cpuinfo)):
        assert get_cpu_type() == expected_cpu_type
    get_cpu_type.cache_clear()


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


def test_blueos_version(monkeypatch: pytest.MonkeyPatch) -> None:
    general.blueos_version.cache_clear()
    monkeypatch.setenv("GIT_DESCRIBE_TAGS", "1.5.0-10-gabcdef12")
    assert general.blueos_version() == "1.5.0-10-gabcdef12"
    general.blueos_version.cache_clear()
    monkeypatch.delenv("GIT_DESCRIBE_TAGS")
    assert general.blueos_version() == "null"
    general.blueos_version.cache_clear()


@pytest.mark.parametrize(
    "returncode,stdout,stderr,expected",
    [
        (0, "1234", "", True),  # lsof listed a PID holding the file
        (0, "", "", False),  # lsof succeeded but nothing holds the file
        (1, "", "", False),  # lsof exit 1 with clean stderr: file not open
        (1, "", "lsof: status error", True),  # lsof failed: assume open to stay safe
        (None, "", "", True),  # no return code: assume open to stay safe
    ],
)
def test_file_is_open_logic_lsof(returncode: int | None, stdout: str, stderr: str, expected: bool) -> None:
    assert general._file_is_open_logic_lsof(returncode, stdout, stderr) is expected


def test_file_is_open_command(tmp_path: Path) -> None:
    target = tmp_path / "some.file"
    command = general._file_is_open_command(target)
    assert command[0] == "lsof"
    assert command[-1] == str(target.resolve())


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


@pytest.mark.asyncio
async def test_file_is_open_async(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")
    assert await general.file_is_open_async(target) is False
    with open(target, "r", encoding="utf-8"):
        assert await general.file_is_open_async(target) is True


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

    # .gz files are deleted even while a process holds them open
    with open(rotated_log, "r", encoding="utf-8"):
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
