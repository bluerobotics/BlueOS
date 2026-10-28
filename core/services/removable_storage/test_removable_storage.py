import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))
_saved = sys.modules.pop("main", None)

import main as removable_storage

if _saved is not None:
    sys.modules["main"] = _saved
else:
    sys.modules.pop("main", None)


def lsblk_payload() -> str:
    return json.dumps(
        {
            "blockdevices": [
                {
                    "name": "/dev/mmcblk0",
                    "kname": "/dev/mmcblk0",
                    "path": "/dev/mmcblk0",
                    "type": "disk",
                    "tran": None,
                    "children": [
                        {
                            "name": "/dev/mmcblk0p2",
                            "kname": "/dev/mmcblk0p2",
                            "path": "/dev/mmcblk0p2",
                            "type": "part",
                            "fstype": "ext4",
                            "size": 1000,
                            "mountpoints": ["/"],
                        }
                    ],
                },
                {
                    "name": "/dev/sda",
                    "kname": "/dev/sda",
                    "path": "/dev/sda",
                    "type": "disk",
                    "tran": "usb",
                    "children": [
                        {
                            "name": "/dev/sda1",
                            "kname": "/dev/sda1",
                            "path": "/dev/sda1",
                            "type": "part",
                            "fstype": "vfat",
                            "label": "Dive Logs",
                            "uuid": "ABCD",
                            "size": 4096,
                            "mountpoints": [None],
                            "ro": False,
                        },
                        {
                            "name": "/dev/sda2",
                            "kname": "/dev/sda2",
                            "path": "/dev/sda2",
                            "type": "part",
                            "fstype": "ext4",
                            "label": "Dive Logs",
                            "uuid": "EFGH",
                            "size": 8192,
                            "mountpoints": ["/media/pi/logs"],
                            "ro": False,
                        },
                    ],
                },
            ]
        }
    )


def completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args="", returncode=returncode, stdout=stdout, stderr=stderr)


def device(mounted: bool = False, managed: bool = False) -> removable_storage.StorageDevice:
    mount_point = "/usr/blueos/userdata/removable/Dive-Logs-ABCD" if mounted else None
    return removable_storage.StorageDevice(
        path="/dev/sda1",
        name="Dive-Logs-ABCD",
        label="Dive Logs",
        uuid="ABCD",
        filesystem="vfat",
        size_bytes=4096,
        mount_point=mount_point,
        mounted=mounted,
        managed=managed,
        read_only=False,
        writable=mounted and managed,
    )


def test_parse_lsblk_only_returns_safe_usb_filesystems() -> None:
    devices = removable_storage.parse_lsblk(lsblk_payload())
    assert [item.path for item in devices] == ["/dev/sda1", "/dev/sda2"]
    assert [item.name for item in devices] == ["Dive-Logs-ABCD", "Dive-Logs-EFGH"]
    assert devices[0].mount_point is None
    assert devices[1].mount_point == "/media/pi/logs"
    assert not devices[1].managed


def test_parse_lsblk_rejects_entire_usb_system_disk() -> None:
    payload = json.loads(lsblk_payload())
    payload["blockdevices"][1]["children"][0]["mountpoints"] = ["/boot"]
    assert not removable_storage.parse_lsblk(json.dumps(payload))


@pytest.mark.parametrize("filesystem", sorted(removable_storage.NON_MOUNTABLE_FILESYSTEMS))
def test_parse_lsblk_skips_filesystems_holding_no_data(filesystem: str) -> None:
    payload = json.loads(lsblk_payload())
    for partition in payload["blockdevices"][1]["children"]:
        partition["fstype"] = filesystem
    assert not removable_storage.parse_lsblk(json.dumps(payload))


def test_parse_lsblk_names_unlabeled_device_after_its_kname() -> None:
    payload = json.loads(lsblk_payload())
    partition = payload["blockdevices"][1]["children"][0]
    del partition["label"]
    del partition["uuid"]
    assert removable_storage.parse_lsblk(json.dumps(payload))[0].name == "sda1"


@pytest.mark.parametrize(
    "value, expected",
    [
        (" Dive Logs ", "Dive-Logs"),
        ("../../bad name", "bad-name"),
        ("", "usb-storage"),
        ("a" * 80, "a" * 64),
    ],
)
def test_safe_name(value: str, expected: str) -> None:
    assert removable_storage.safe_name(value) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/usr/blueos/userdata/removable/disk", True),
        ("/usr/blueos/userdata/removable", False),
        ("/usr/blueos/userdata/removable-disk", False),
        ("/media/disk", False),
    ],
)
def test_is_managed_mount(path: str, expected: bool) -> None:
    assert removable_storage.is_managed_mount(path) is expected


@pytest.mark.asyncio
async def test_discover_devices_handles_host_and_json_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def host_error(_command: str) -> subprocess.CompletedProcess[str]:
        return completed(1, stderr="lsblk failed")

    monkeypatch.setattr(removable_storage, "run_host", host_error)
    with pytest.raises(HTTPException, match="lsblk failed") as error:
        await removable_storage.discover_devices()
    assert error.value.status_code == 503

    async def invalid_json(_command: str) -> subprocess.CompletedProcess[str]:
        return completed(stdout="not json")

    monkeypatch.setattr(removable_storage, "run_host", invalid_json)
    with pytest.raises(HTTPException, match="invalid block-device") as error:
        await removable_storage.discover_devices()
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_mount_device_uses_fixed_options_and_managed_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discoveries = iter([[device()], [device(mounted=True, managed=True)]])
    commands: list[str] = []

    async def discover() -> list[removable_storage.StorageDevice]:
        return next(discoveries)

    async def run(command: str) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return completed()

    monkeypatch.setattr(removable_storage, "discover_devices", discover)
    monkeypatch.setattr(removable_storage, "run_host", run)
    result = await removable_storage.mount_device(removable_storage.DeviceRequest(path="/dev/sda1"))
    assert result.writable
    assert "rw,nosuid,nodev,noexec" in commands[0]
    assert "/usr/blueos/userdata/removable/Dive-Logs-ABCD" in commands[0]


@pytest.mark.asyncio
async def test_mount_device_rejects_unknown_or_external_mount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing() -> list[removable_storage.StorageDevice]:
        return []

    monkeypatch.setattr(removable_storage, "discover_devices", missing)
    with pytest.raises(HTTPException) as error:
        await removable_storage.mount_device(removable_storage.DeviceRequest(path="/dev/root"))
    assert error.value.status_code == 404

    external = device(mounted=True)
    external.mount_point = "/media/pi/disk"

    async def outside() -> list[removable_storage.StorageDevice]:
        return [external]

    monkeypatch.setattr(removable_storage, "discover_devices", outside)
    with pytest.raises(HTTPException) as error:
        await removable_storage.mount_device(removable_storage.DeviceRequest(path="/dev/sda1"))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_unmount_device_reports_busy_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def discover() -> list[removable_storage.StorageDevice]:
        return [device(mounted=True, managed=True)]

    async def run(_command: str) -> subprocess.CompletedProcess[str]:
        return completed(32, stderr="target is busy")

    monkeypatch.setattr(removable_storage, "discover_devices", discover)
    monkeypatch.setattr(removable_storage, "run_host", run)
    with pytest.raises(HTTPException, match="target is busy") as error:
        await removable_storage.unmount_device(removable_storage.DeviceRequest(path="/dev/sda1"))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_unmount_succeeds_if_device_disappears_after_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def discover() -> list[removable_storage.StorageDevice]:
        return [device(mounted=True, managed=True)]

    async def run(_command: str) -> subprocess.CompletedProcess[str]:
        return completed()

    monkeypatch.setattr(removable_storage, "discover_devices", discover)
    monkeypatch.setattr(removable_storage, "run_host", run)
    result = await removable_storage.unmount_device(removable_storage.DeviceRequest(path="/dev/sda1"))
    assert not result.mounted
    assert result.mount_point is None
