#! /usr/bin/env python3

import asyncio
import json
import logging
import re
import shlex
import subprocess
from pathlib import PurePosixPath
from typing import Any, Optional

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.commands import run_command
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from pydantic import BaseModel, Field
from uvicorn import Config, Server

SERVICE_NAME = "removable-storage"
PORT = 9153
MOUNT_ROOT = PurePosixPath("/usr/blueos/userdata/removable")
MOUNT_OPTIONS = "rw,nosuid,nodev,noexec"
PROTECTED_MOUNT_POINTS = {"/", "/boot", "/boot/firmware"}
# Signatures that lsblk reports as a filesystem but that hold no mountable data
NON_MOUNTABLE_FILESYSTEMS = {"crypto_LUKS", "LVM2_member", "linux_raid_member", "swap", "zfs_member"}
LSBLK_COMMAND = [
    "lsblk",
    "--json",
    "--bytes",
    "--paths",
    "--output",
    "NAME,KNAME,PATH,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINT,RO,RM,TRAN",
]

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Removable Storage service")


class StorageDevice(BaseModel):
    path: str
    name: str
    label: Optional[str] = None
    uuid: Optional[str] = None
    filesystem: str
    size_bytes: int
    mount_point: Optional[str] = None
    mounted: bool
    managed: bool
    read_only: bool
    writable: bool


class DevicesResponse(BaseModel):
    devices: list[StorageDevice]


class DeviceRequest(BaseModel):
    path: str = Field(..., examples=["/dev/sda1"])


mount_lock = asyncio.Lock()


async def run_host(command: str) -> subprocess.CompletedProcess[str]:
    return await asyncio.to_thread(run_command, command, False, False)


def command_error(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    return (result.stderr or result.stdout or fallback).strip()


def mount_points(node: dict[str, Any]) -> list[str]:
    value = node.get("mountpoints")
    if value is None:
        value = node.get("mountpoint")
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [item for item in value if item]


def contains_protected_mount(node: dict[str, Any]) -> bool:
    if any(point in PROTECTED_MOUNT_POINTS for point in mount_points(node)):
        return True
    return any(contains_protected_mount(child) for child in node.get("children") or [])


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return name[:64] or "usb-storage"


def is_managed_mount(mount_point: str) -> bool:
    path = PurePosixPath(mount_point)
    return path != MOUNT_ROOT and path.is_relative_to(MOUNT_ROOT)


def device_name(node: dict[str, Any], path: str, used_names: set[str]) -> str:
    # --paths makes lsblk report kname as a full path as well
    kname = PurePosixPath(node.get("kname") or path).name
    identifier = node.get("uuid") or kname
    name = safe_name(f"{node['label']}-{identifier}" if node.get("label") else identifier)
    return name if name not in used_names else safe_name(f"{name}-{kname}")


def parse_lsblk(payload: str) -> list[StorageDevice]:
    try:
        root_nodes = json.loads(payload)["blockdevices"]
    except (json.JSONDecodeError, KeyError, TypeError) as exception:
        raise ValueError("Host returned invalid block-device data.") from exception

    devices: list[StorageDevice] = []
    used_names: set[str] = set()

    def visit(node: dict[str, Any], usb_ancestor: bool, blocked_disk: bool) -> None:
        is_usb = usb_ancestor or node.get("tran") == "usb"
        filesystem = node.get("fstype")
        path = node.get("path") or node.get("name")
        points = mount_points(node)

        mountable = filesystem and filesystem not in NON_MOUNTABLE_FILESYSTEMS
        if is_usb and not blocked_disk and mountable and path and node.get("type") in {"disk", "part"}:
            name = device_name(node, path, used_names)
            used_names.add(name)
            managed_point = next((point for point in points if is_managed_mount(point)), None)
            mount_point = managed_point or (points[0] if points else None)
            read_only = bool(node.get("ro"))
            managed = managed_point is not None
            devices.append(
                StorageDevice(
                    path=path,
                    name=name,
                    label=node.get("label"),
                    uuid=node.get("uuid"),
                    filesystem=filesystem,
                    size_bytes=int(node.get("size") or 0),
                    mount_point=mount_point,
                    mounted=mount_point is not None,
                    managed=managed,
                    read_only=read_only,
                    writable=managed and not read_only,
                )
            )

        for child in node.get("children") or []:
            visit(child, is_usb, blocked_disk)

    for root_node in root_nodes:
        visit(root_node, False, contains_protected_mount(root_node))
    return devices


async def discover_devices() -> list[StorageDevice]:
    result = await run_host(shlex.join(LSBLK_COMMAND))
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=command_error(result, "Unable to inspect host block devices."),
        )
    try:
        return parse_lsblk(result.stdout)
    except ValueError as exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exception)) from exception


def find_device(devices: list[StorageDevice], path: str) -> StorageDevice:
    try:
        return next(device for device in devices if device.path == path)
    except StopIteration as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="USB storage device was not found or is not safe to manage.",
        ) from exception


storage_router = APIRouter(
    tags=["removable_storage_v1"],
    route_class=versioned_api_route(1, 0),
)


@storage_router.get("/devices", response_model=DevicesResponse)
async def get_devices() -> DevicesResponse:
    return DevicesResponse(devices=await discover_devices())


@storage_router.post("/devices/mount", response_model=StorageDevice)
async def mount_device(request: DeviceRequest) -> StorageDevice:
    async with mount_lock:
        device = find_device(await discover_devices(), request.path)
        if device.mounted:
            if device.managed:
                return device
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{device.path} is already mounted outside BlueOS at {device.mount_point}.",
            )
        if device.read_only:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{device.path} is read-only.",
            )

        target = MOUNT_ROOT / device.name
        command = (
            f"sudo mkdir -p -- {shlex.quote(str(target))} && "
            f"sudo mount -o {shlex.quote(MOUNT_OPTIONS)} -- "
            f"{shlex.quote(device.path)} {shlex.quote(str(target))}"
        )
        result = await run_host(command)
        if result.returncode != 0:
            cleanup = f"sudo rmdir -- {shlex.quote(str(target))} 2>/dev/null || true"
            await run_host(cleanup)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=command_error(result, f"Failed to mount {device.path}."),
            )

        return find_device(await discover_devices(), request.path)


@storage_router.post("/devices/unmount", response_model=StorageDevice)
async def unmount_device(request: DeviceRequest) -> StorageDevice:
    async with mount_lock:
        device = find_device(await discover_devices(), request.path)
        if not device.mounted:
            return device
        if not device.managed or not device.mount_point:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{device.path} is mounted outside BlueOS and cannot be unmounted here.",
            )

        target = PurePosixPath(device.mount_point)
        if not is_managed_mount(str(target)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid managed mount point.",
            )
        command = (
            f"sudo umount -- {shlex.quote(str(target))} && "
            f"(sudo rmdir -- {shlex.quote(str(target))} 2>/dev/null || true)"
        )
        result = await run_host(command)
        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=command_error(result, f"Failed to unmount {device.path}; the device may be busy."),
            )

        return device.model_copy(
            update={
                "mount_point": None,
                "mounted": False,
                "managed": False,
                "writable": False,
            }
        )


fast_api_app = FastAPI(
    title="Removable Storage API",
    description="Discover and manage writable USB storage devices.",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute
fast_api_app.include_router(storage_router)

app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": SERVICE_NAME}


async def main() -> None:
    try:
        await init_sentry_async(SERVICE_NAME)
        await Server(Config(app=app, host="0.0.0.0", port=PORT, log_config=None)).serve()
    finally:
        logger.info("Removable Storage service stopped")


if __name__ == "__main__":
    asyncio.run(main())
