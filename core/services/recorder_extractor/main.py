#! /usr/bin/env python3

import asyncio
import logging
import os
import re
import shutil
import struct
import tempfile
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Set
from urllib.parse import quote

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.general import file_is_open_async, open_files_under
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

SERVICE_NAME = "recorder-extractor"
RECORDER_DIR = Path("/usr/blueos/userdata/recorder")
RECORDER_URL = "/userdata/recorder"
PORT = 9150
RECORDING_SUFFIX = ".mcap"

MCAP_MAGIC = b"\x89MCAP0\r\n"
MCAP_FOOTER_SIZE = 29

RECENTLY_WRITTEN_SECONDS = 10

SPLIT_TIMESTAMP_PATTERN = re.compile(r"_split_(\d{8})_(\d{6})\.mcap$", re.IGNORECASE)
RECORDER_TIMESTAMP_PATTERN = re.compile(r"^recorder_(\d{8})_(\d{6})")

RecordingState = Literal["recording", "ready", "needs_repair", "repairing"]

processing_mcap_files: set[str] = set()
splitting_source_paths: set[str] = set()
repair_failures: Dict[str, str] = {}
processing_tasks: Set["asyncio.Task[None]"] = set()
# Resolved path -> (inode, size, mtime_ns, footer). Finished files do not grow, so the footer
# is reused until the file is replaced or deleted.
recording_footer_cache: Dict[str, tuple[int, int, int, tuple[int, int] | None]] = {}

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Recorder Extractor service")


class RepairFailed(Exception):
    """A recording could not be given its index back."""


class RecordingFile(BaseModel):
    name: str
    path: str
    size_bytes: int
    created: float
    state: RecordingState
    download_url: str
    stream_url: str


class ProcessingFile(BaseModel):
    name: str
    path: str


class FailedRepair(BaseModel):
    name: str
    path: str
    error: str


class ProcessingStatus(BaseModel):
    processing: List[ProcessingFile]
    failed: List[FailedRepair] = []


class SplitRecordingResponse(BaseModel):
    recording: RecordingFile
    status: ProcessingStatus


def ensure_recorder_dir() -> Path:
    RECORDER_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDER_DIR.resolve()


def resolve_recording(filename: str) -> Path:
    base = ensure_recorder_dir()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        logger.warning(f"Path resolve attempt: base={base} candidate={candidate} raw={filename}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording path.") from exc

    if candidate.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording path.")
    if candidate.suffix.lower() != RECORDING_SUFFIX:
        logger.warning(f"Rejected unsupported path: {candidate}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {RECORDING_SUFFIX} recordings are supported.",
        )
    if not candidate.exists() or not candidate.is_file():
        logger.warning(f"Recording not found: {candidate}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found.")
    return candidate


def parse_utc_timestamp(date_part: str, time_part: str) -> float:
    parsed = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def created_from_filename(name: str, stat: os.stat_result) -> float:
    split_match = SPLIT_TIMESTAMP_PATTERN.search(name)
    if split_match:
        return parse_utc_timestamp(split_match.group(1), split_match.group(2))
    recorder_match = RECORDER_TIMESTAMP_PATTERN.match(name)
    if recorder_match:
        return parse_utc_timestamp(recorder_match.group(1), recorder_match.group(2))
    return stat.st_ctime or stat.st_mtime


def read_mcap_footer(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
    try:
        if size is None:
            size = mcap_path.stat().st_size
        if size < (len(MCAP_MAGIC) * 2) + MCAP_FOOTER_SIZE:
            return None
        with mcap_path.open("rb") as recording:
            recording.seek(size - len(MCAP_MAGIC) - MCAP_FOOTER_SIZE)
            footer = recording.read(MCAP_FOOTER_SIZE + len(MCAP_MAGIC))
    except OSError as exception:
        logger.warning(f"Failed to read MCAP footer of {mcap_path}: {exception}")
        return None

    if len(footer) != MCAP_FOOTER_SIZE + len(MCAP_MAGIC) or not footer.endswith(MCAP_MAGIC):
        return None
    summary_start = struct.unpack_from("<Q", footer, 9)[0]
    summary_offset_start = struct.unpack_from("<Q", footer, 17)[0]
    return summary_start, summary_offset_start


def mcap_is_indexed(mcap_path: Path) -> bool:
    footer = read_mcap_footer(mcap_path)
    return footer is not None and footer[0] > 0


def footer_for_listing(path: Path, stat: os.stat_result, *, is_open: bool) -> tuple[int, int] | None:
    if is_open:
        return None
    cache_key = str(path.resolve())
    identity = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    cached = recording_footer_cache.get(cache_key)
    if cached is not None and cached[:3] == identity:
        return cached[3]
    footer = read_mcap_footer(path, size=stat.st_size)
    recording_footer_cache[cache_key] = (*identity, footer)
    return footer


def prune_recording_footer_cache(keep: set[str]) -> None:
    for cache_key in [key for key in recording_footer_cache if key not in keep]:
        recording_footer_cache.pop(cache_key, None)


def recording_state(relative_path: str, is_open: bool, footer: tuple[int, int] | None) -> RecordingState:
    if relative_path in processing_mcap_files:
        return "repairing"
    if is_open:
        return "recording"
    if footer is not None and footer[0] > 0:
        return "ready"
    return "needs_repair"


async def recording_is_open(path: Path, open_files: set[Path] | None) -> bool:
    if open_files is None:
        return await file_is_open_async(path)
    return path.resolve() in open_files


async def build_recording_file(path: Path, base_path: Path, *, is_open: bool | None = None) -> RecordingFile:
    stat = path.stat()
    relative_path = str(path.relative_to(base_path))
    if is_open is None:
        is_open = await file_is_open_async(path)

    created = created_from_filename(path.name, stat)
    footer = footer_for_listing(path, stat, is_open=is_open)
    state = recording_state(relative_path, is_open, footer)
    recording_url = f"{RECORDER_URL}/{quote(relative_path)}"
    return RecordingFile(
        name=path.name,
        path=relative_path,
        size_bytes=stat.st_size,
        created=created,
        state=state,
        download_url=recording_url,
        stream_url=recording_url,
    )


async def recover_mcap(mcap_path: Path) -> None:
    mcap_binary = shutil.which("mcap")
    if not mcap_binary:
        raise RepairFailed("The mcap tool is not available on this vehicle.")

    if not mcap_path.exists() or not mcap_path.is_file():
        raise RepairFailed("The recording is gone.")

    logger.info(f"Attempting to recover {mcap_path}")

    with tempfile.NamedTemporaryFile(delete=False, dir=mcap_path.parent, suffix=".recover") as tmpfile:
        tmp_path = Path(tmpfile.name)
    try:
        await write_recovered_mcap(mcap_binary, mcap_path, tmp_path)
    except RepairFailed:
        raise
    except OSError as exception:
        logger.error(f"Failed to replace original file after mcap recover: {exception}")
        raise RepairFailed(f"Could not put the repaired recording in place: {exception}") from exception
    except Exception as exception:
        logger.exception(f"Unexpected error during mcap recover: {exception}")
        raise RepairFailed(str(exception)) from exception
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as exception:
                logger.error(f"Failed to clean up temporary file {tmp_path}: {exception}")


async def write_recovered_mcap(mcap_binary: str, mcap_path: Path, tmp_path: Path) -> None:
    recover_cmd = [mcap_binary, "recover", str(mcap_path), "-o", str(tmp_path)]
    recover_proc = await asyncio.create_subprocess_exec(
        *recover_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    _, recover_stderr_bytes = await recover_proc.communicate()
    recover_stderr = recover_stderr_bytes.decode("utf-8", "ignore")

    if recover_proc.returncode != 0:
        logger.error(
            f"mcap recover command failed for {mcap_path} (code={recover_proc.returncode}): {recover_stderr.strip()}",
        )
        reason = recover_stderr.strip().splitlines()[-1:]
        raise RepairFailed(reason[0] if reason else f"mcap recover exited with {recover_proc.returncode}.")

    if not tmp_path.exists():
        raise RepairFailed("mcap recover wrote no recording.")

    if tmp_path.stat().st_size == 0:
        raise RepairFailed("mcap recover found nothing worth keeping in this recording.")

    original = mcap_path.stat()
    os.chmod(tmp_path, original.st_mode & 0o777)
    try:
        os.chown(tmp_path, original.st_uid, original.st_gid)
    except PermissionError:
        logger.warning(f"Cannot keep the owner of {mcap_path}, the repaired file stays with ours")

    tmp_path.replace(mcap_path)
    logger.info(f"Successfully recovered {mcap_path} (recovered size: {mcap_path.stat().st_size} bytes)")


async def process_recording(mcap_path: Path, relative_path: str) -> None:
    try:
        await recover_mcap(mcap_path)
    except RepairFailed as failure:
        logger.error(f"Repair of {relative_path} failed: {failure}")
        repair_failures[relative_path] = str(failure)
    finally:
        processing_mcap_files.discard(relative_path)


def current_status() -> ProcessingStatus:
    return ProcessingStatus(
        processing=[ProcessingFile(name=Path(path).name, path=path) for path in list(processing_mcap_files)],
        failed=[
            FailedRepair(name=Path(path).name, path=path, error=error) for path, error in list(repair_failures.items())
        ],
    )


def split_destination_path(source_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return source_path.with_name(f"{source_path.stem}_split_{timestamp}{RECORDING_SUFFIX}")


def copy_recording_prefix(source_path: Path, destination_path: Path) -> None:
    source_size = source_path.stat().st_size
    with source_path.open("rb") as source, destination_path.open("wb") as destination:
        remaining = source_size
        offset = 0
        while remaining > 0:
            sent = os.sendfile(destination.fileno(), source.fileno(), offset, remaining)
            if sent == 0:
                break
            offset += sent
            remaining -= sent


def ensure_disk_space_for_split(directory: Path, source_size: int) -> None:
    free_bytes = shutil.disk_usage(directory).free
    if free_bytes < source_size:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough disk space to snapshot this recording.",
        )


async def snapshot_copy_recording(source_path: Path, destination_path: Path) -> None:
    ensure_disk_space_for_split(destination_path.parent, source_path.stat().st_size)
    try:
        await asyncio.to_thread(copy_recording_prefix, source_path, destination_path)
    except Exception:
        if destination_path.exists():
            try:
                destination_path.unlink()
            except OSError as exception:
                logger.error(f"Failed to remove partial split recording {destination_path}: {exception}")
        raise


async def recover_split_recording(split_path: Path, split_relative_path: str) -> None:
    try:
        await recover_mcap(split_path)
    except RepairFailed as failure:
        logger.error(f"Split recover of {split_relative_path} failed: {failure}")
        repair_failures[split_relative_path] = str(failure)
        if split_path.exists():
            try:
                split_path.unlink()
            except OSError as exception:
                logger.error(f"Failed to remove failed split recording {split_path}: {exception}")
    finally:
        processing_mcap_files.discard(split_relative_path)


def to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
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
            logger.exception("Recorder endpoint failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exception)) from exception

    return wrapper


recorder_router = APIRouter(
    tags=["recorder_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@recorder_router.get(
    "/files",
    response_model=List[RecordingFile],
    summary="List available recordings under /usr/blueos/userdata/recorder.",
)
@to_http_exception
async def list_recordings() -> List[RecordingFile]:
    base_path = ensure_recorder_dir()
    recording_paths = list(base_path.rglob(f"*{RECORDING_SUFFIX}"))
    open_files = await asyncio.to_thread(open_files_under, base_path)
    files: List[RecordingFile] = []
    listed_paths: set[str] = set()
    for path in recording_paths:
        try:
            is_open = await recording_is_open(path, open_files)
            files.append(await build_recording_file(path, base_path, is_open=is_open))
            listed_paths.add(str(path.resolve()))
        except FileNotFoundError:
            continue
    prune_recording_footer_cache(listed_paths)
    return sorted(files, key=lambda recording: recording.created, reverse=True)


@recorder_router.get(
    "/status",
    response_model=ProcessingStatus,
    summary="Get MCAP repair and split status.",
)
@to_http_exception
async def get_processing_status() -> ProcessingStatus:
    return current_status()


@recorder_router.post(
    "/files/{filename:path}/repair",
    response_model=ProcessingStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Give a recording its MCAP index back.",
)
@to_http_exception
async def repair_recording_request(filename: str) -> ProcessingStatus:
    path = resolve_recording(filename)
    relative_path = str(path.relative_to(ensure_recorder_dir()))
    if relative_path in processing_mcap_files:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording is already being repaired.",
        )

    if mcap_is_indexed(path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording already has an index.",
        )

    written_seconds_ago = time.time() - path.stat().st_mtime
    if written_seconds_ago < RECENTLY_WRITTEN_SECONDS or await file_is_open_async(path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording is still being written. Try again once it is finished.",
        )

    processing_mcap_files.add(relative_path)
    repair_failures.pop(relative_path, None)
    task = asyncio.create_task(process_recording(path, relative_path))
    processing_tasks.add(task)
    task.add_done_callback(processing_tasks.discard)
    return current_status()


@recorder_router.post(
    "/files/{filename:path}/split",
    response_model=SplitRecordingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Snapshot a live recording into a seekable split file.",
)
@to_http_exception
async def split_recording_request(filename: str) -> SplitRecordingResponse:
    source_path = resolve_recording(filename)
    relative_path = str(source_path.relative_to(ensure_recorder_dir()))
    if relative_path in processing_mcap_files or relative_path in splitting_source_paths:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording is already being processed.",
        )

    split_path = split_destination_path(source_path)
    if split_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A split recording with this name already exists.",
        )

    split_relative_path = str(split_path.relative_to(ensure_recorder_dir()))
    splitting_source_paths.add(relative_path)
    try:
        await snapshot_copy_recording(source_path, split_path)
    finally:
        splitting_source_paths.discard(relative_path)
    processing_mcap_files.add(split_relative_path)
    repair_failures.pop(split_relative_path, None)
    task = asyncio.create_task(recover_split_recording(split_path, split_relative_path))
    processing_tasks.add(task)
    task.add_done_callback(processing_tasks.discard)

    recording = await build_recording_file(split_path, ensure_recorder_dir(), is_open=False)
    return SplitRecordingResponse(recording=recording, status=current_status())


@recorder_router.delete(
    "/files/{filename:path}",
    summary="Delete a recording.",
    status_code=status.HTTP_204_NO_CONTENT,
)
@to_http_exception
async def delete_recording(filename: str) -> None:
    path = resolve_recording(filename)
    relative_path = str(path.relative_to(ensure_recorder_dir()))
    if relative_path in processing_mcap_files:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording is being processed.",
        )
    if await file_is_open_async(path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recording is still being written.",
        )
    try:
        path.unlink()
    except Exception as exception:
        logger.exception(f"Failed to delete recording {filename}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete recording.",
        ) from exception


fast_api_app = FastAPI(
    title="Recorder Extractor API",
    description="Catalog MCAP recordings and keep them seekable. Their bytes are served by nginx.",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute
fast_api_app.include_router(recorder_router)

app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)


@app.get("/")
async def root() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>Recorder Extractor</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
    server = Server(config)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
