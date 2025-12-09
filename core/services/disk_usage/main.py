#! /usr/bin/env python3

import asyncio
import logging
import shutil
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from pydantic import BaseModel, Field
from uvicorn import Config, Server

SERVICE_NAME = "disk-usage"
FILESYSTEM_ROOT = Path("/")
PORT = 9151
DEFAULT_DEPTH = 2
DEFAULT_MIN_SIZE_BYTES = 0

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Disk Usage service")


class DiskNode(BaseModel):
    name: str
    path: str
    size_bytes: int
    is_dir: bool
    children: List["DiskNode"] = Field(default_factory=list)


class DiskUsageResponse(BaseModel):
    root: DiskNode
    generated_at: float
    depth: int
    include_files: bool
    min_size_bytes: int


DiskNode.update_forward_refs()


def to_http_exception(endpoint: Any) -> Any:
    is_async = asyncio.iscoroutinefunction(endpoint)

    @wraps(endpoint)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            if is_async:
                return await endpoint(*args, **kwargs)
            return endpoint(*args, **kwargs)
        except HTTPException as exception:
            raise exception
        except Exception as exception:
            logger.exception("Disk Usage endpoint failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exception)) from exception

    return wrapper


def resolve_requested_path(requested_path: str | None) -> Path:
    path = Path(requested_path or "/")
    if not path.is_absolute():
        path = (FILESYSTEM_ROOT / path).resolve()
    try:
        resolved = path.resolve()
    except FileNotFoundError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found.") from exception
    try:
        resolved.relative_to(FILESYSTEM_ROOT)
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path outside filesystem root."
        ) from exception
    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found.")
    return resolved


def is_protected_target(path: Path) -> bool:
    protected_roots = {
        Path("/bin"),
        Path("/boot"),
        Path("/dev"),
        Path("/etc"),
        Path("/lib"),
        Path("/lib64"),
        Path("/proc"),
        Path("/run"),
        Path("/sbin"),
        Path("/sys"),
        Path("/usr/bin"),
        Path("/usr/lib"),
        Path("/usr/libexec"),
        Path("/usr/sbin"),
    }
    for root_path in protected_roots:
        try:
            path.relative_to(root_path)
            return True
        except ValueError:
            continue
    return False


def build_tree(entries: Dict[Path, int], root_path: Path, min_size_bytes: int) -> DiskNode:
    if root_path not in entries:
        try:
            aggregated = sum(
                size for path, size in entries.items() if path == root_path or path.is_relative_to(root_path)
            )
            entries[root_path] = aggregated if aggregated > 0 else root_path.stat().st_size
        except FileNotFoundError:
            entries[root_path] = 0

    nodes: Dict[Path, DiskNode] = {}
    sorted_paths = sorted(entries.keys(), key=lambda path: len(path.parts))
    for path in sorted_paths:
        size = entries[path]
        if path != root_path and size < min_size_bytes:
            continue

        is_dir = path.is_dir()
        display_name = "/" if path == root_path else path.name
        nodes[path] = DiskNode(
            name=display_name,
            path=str(path),
            size_bytes=size,
            is_dir=is_dir,
            children=[],
        )

    for path, node in nodes.items():
        if path == root_path:
            continue
        parent = path.parent
        while parent not in nodes and parent != parent.parent:
            parent = parent.parent
        if parent in nodes:
            nodes[parent].children.append(node)

    for node in nodes.values():
        node.children.sort(key=lambda child: child.size_bytes, reverse=True)

    return nodes[root_path]


def parse_du_output(output: bytes) -> Dict[Path, int]:
    entries: Dict[Path, int] = {}
    for line in output.decode("utf-8", "ignore").splitlines():
        if not line.strip():
            continue
        try:
            size_str, raw_path = line.split("\t", 1)
        except ValueError:
            try:
                size_str, raw_path = line.split(maxsplit=1)
            except ValueError:
                logger.debug(f"Skipping malformed du line: {line}")
                continue
        try:
            size = int(size_str)
        except ValueError:
            logger.debug(f"Skipping malformed size for line: {line}")
            continue
        entry_path = Path(raw_path)
        try:
            resolved = entry_path.resolve()
        except (FileNotFoundError, OSError, RuntimeError):
            # Skip entries that cannot be resolved (broken/looping symlinks, missing files, loops)
            continue
        entries[resolved] = size
    return entries


async def collect_disk_usage(
    path: Path,
    depth: int,
    include_files: bool,
    min_size_bytes: int,
) -> DiskUsageResponse:
    args = ["du", "-b", str(path)]
    if include_files:
        args.insert(1, "-a")
    if depth >= 0:
        args.extend(["-d", str(depth)])

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    if process.returncode not in (0, 1):
        stderr = stderr_bytes.decode("utf-8", "ignore")
        logger.warning(f"du command returned {process.returncode}: {stderr}")

    entries = parse_du_output(stdout_bytes)
    tree = build_tree(entries, path, min_size_bytes)

    return DiskUsageResponse(
        root=tree,
        generated_at=time.time(),
        depth=depth,
        include_files=include_files,
        min_size_bytes=min_size_bytes,
    )


disk_router = APIRouter(
    prefix="/disk",
    tags=["disk_usage_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@disk_router.get(
    "/usage",
    response_model=DiskUsageResponse,
    summary="Get disk usage tree for a given path using du.",
)
@to_http_exception
async def get_disk_usage(
    path: str = Query("/", description="Path to inspect, defaults to filesystem root."),
    depth: int = Query(DEFAULT_DEPTH, ge=0, description="Max depth to request from du."),
    include_files: bool = Query(True, description="Include files in the output."),
    min_size_bytes: int = Query(
        DEFAULT_MIN_SIZE_BYTES,
        ge=0,
        description="Filter out entries smaller than this size (except for the root).",
    ),
) -> DiskUsageResponse:
    resolved_path = resolve_requested_path(path)
    return await collect_disk_usage(resolved_path, depth, include_files, min_size_bytes)


@disk_router.delete(
    "/paths/{target_path:path}",
    summary="Delete a file or folder recursively.",
    status_code=status.HTTP_204_NO_CONTENT,
)
@to_http_exception
async def delete_path(target_path: str) -> None:
    resolved_path = resolve_requested_path(target_path)

    if is_protected_target(resolved_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refusing to delete protected path.")

    if resolved_path.is_dir():
        shutil.rmtree(resolved_path)
    else:
        resolved_path.unlink()


fast_api_app = FastAPI(
    title="Disk Usage API",
    description="Inspect disk usage and delete files using du.",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute
fast_api_app.include_router(disk_router)

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

        config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
        server = Server(config)

        await server.serve()
    finally:
        logger.info("Disk Usage service stopped")


if __name__ == "__main__":
    asyncio.run(main())
