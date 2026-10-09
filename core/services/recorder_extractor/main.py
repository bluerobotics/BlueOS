#! /usr/bin/env python3

import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Set
from urllib.parse import quote

from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.general import file_is_open_async, open_files_under
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from mcap_index import (
    RecordingIndex,
    footer_for_listing,
    mcap_is_indexed,
    prune_recording_footer_cache,
    walk_mcap_index,
)
from pydantic import BaseModel
from uvicorn import Config, Server

SERVICE_NAME = "recorder-extractor"
RECORDER_DIR = Path("/usr/blueos/userdata/recorder")
RECORDER_URL = "/userdata/recorder"
RECORDER_EXTRACTOR_FILES_URL = "/recorder-extractor/v1.0/files"
PORT = 9150
RECORDING_SUFFIX = ".mcap"

RECENTLY_WRITTEN_SECONDS = 10
RECOVER_SUFFIX = ".recover"

SNAPSHOT_FILENAME_PATTERN = re.compile(
    r"\.snapshot-(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z\.mcap$",
    re.IGNORECASE,
)
COPY_FILENAME_PATTERN = re.compile(
    r"\.copy-(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z\.mcap$",
    re.IGNORECASE,
)
LEGACY_SPLIT_TIMESTAMP_PATTERN = re.compile(r"_split_(\d{8})_(\d{6})\.mcap$", re.IGNORECASE)
RECORDER_TIMESTAMP_PATTERN = re.compile(r"^recorder_(\d{8})_(\d{6})")

RecordingState = Literal["recording", "ready", "needs_repair", "repairing"]


@dataclass
class RepairJob:
    process: asyncio.subprocess.Process | None = None
    bytes_processed: int | None = None
    total_bytes: int | None = None
    bytes_per_second: float | None = None
    cancelled: bool = False
    error: str | None = None


repair_jobs: Dict[str, RepairJob] = {}
processing_tasks: Set["asyncio.Task[None]"] = set()

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
    index_url: str


class ProcessingFile(BaseModel):
    name: str
    path: str
    bytes_processed: int | None = None
    total_bytes: int | None = None
    bytes_per_second: float | None = None


class FailedRepair(BaseModel):
    name: str
    path: str
    error: str


class ProcessingStatus(BaseModel):
    processing: List[ProcessingFile]
    failed: List[FailedRepair] = []


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
    copy_match = COPY_FILENAME_PATTERN.search(name) or SNAPSHOT_FILENAME_PATTERN.search(name)
    if copy_match:
        date_part, hour, minute, second = copy_match.groups()
        return parse_utc_timestamp(date_part.replace("-", ""), f"{hour}{minute}{second}")
    legacy_split_match = LEGACY_SPLIT_TIMESTAMP_PATTERN.search(name)
    if legacy_split_match:
        return parse_utc_timestamp(legacy_split_match.group(1), legacy_split_match.group(2))
    recorder_match = RECORDER_TIMESTAMP_PATTERN.match(name)
    if recorder_match:
        return parse_utc_timestamp(recorder_match.group(1), recorder_match.group(2))
    return stat.st_ctime or stat.st_mtime


def recording_state(relative_path: str, is_open: bool, footer: tuple[int, int] | None) -> RecordingState:
    job = repair_jobs.get(relative_path)
    if job is not None and job.error is None:
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
    # A recording still being written has no MCAP footer, so the raw file looks empty to any
    # indexed reader. Recover a closed copy for download instead of handing over the truncated file.
    download_url = (
        f"{RECORDER_EXTRACTOR_FILES_URL}/{quote(relative_path)}/download" if state == "recording" else recording_url
    )
    return RecordingFile(
        name=path.name,
        path=relative_path,
        size_bytes=stat.st_size,
        created=created,
        state=state,
        download_url=download_url,
        stream_url=recording_url,
        index_url=f"{RECORDER_EXTRACTOR_FILES_URL}/{quote(relative_path)}/index",
    )


def read_input_offset(pid: int, source: Path) -> int | None:
    """How far a process has read a file, taken from the kernel's offset for its descriptor."""
    target = source.resolve()
    try:
        for entry in Path(f"/proc/{pid}/fd").iterdir():
            if entry.resolve() != target:
                continue
            for line in Path(f"/proc/{pid}/fdinfo/{entry.name}").read_text(encoding="utf-8").splitlines():
                if line.startswith("pos:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


async def track_repair_progress(pid: int, source: Path, relative_path: str, total_bytes: int) -> None:
    """Follows `mcap recover` reading the original so the topside can show how far a repair got."""
    started_at = time.monotonic()
    while True:
        offset = read_input_offset(pid, source)
        elapsed = time.monotonic() - started_at
        job = repair_jobs.get(relative_path)
        if job is not None and offset is not None and elapsed > 0:
            read_bytes = min(offset, total_bytes)
            job.bytes_processed = read_bytes
            job.total_bytes = total_bytes
            job.bytes_per_second = read_bytes / elapsed
        await asyncio.sleep(1)


async def start_mcap_recover(source: Path, output: str) -> asyncio.subprocess.Process:
    mcap_binary = shutil.which("mcap")
    if not mcap_binary:
        raise RepairFailed("The mcap tool is not available on this vehicle.")
    return await asyncio.create_subprocess_exec(
        mcap_binary,
        "recover",
        str(source),
        "-o",
        output,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


def raise_if_recover_failed(source: Path, returncode: int | None, stderr: str) -> None:
    if returncode == 0:
        return
    logger.error(f"mcap recover command failed for {source} (code={returncode}): {stderr.strip()}")
    reason = stderr.strip().splitlines()[-1:]
    raise RepairFailed(reason[0] if reason else f"mcap recover exited with {returncode}.")


async def recover_mcap(mcap_path: Path, relative_path: str) -> None:
    if not mcap_path.exists() or not mcap_path.is_file():
        raise RepairFailed("The recording is gone.")

    logger.info(f"Attempting to recover {mcap_path}")

    with tempfile.NamedTemporaryFile(delete=False, dir=mcap_path.parent, suffix=RECOVER_SUFFIX) as tmpfile:
        tmp_path = Path(tmpfile.name)
    try:
        await write_recovered_mcap(mcap_path, tmp_path, relative_path)
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


async def write_recovered_mcap(mcap_path: Path, tmp_path: Path, relative_path: str) -> None:
    recover_proc = await start_mcap_recover(mcap_path, str(tmp_path))
    total_bytes = mcap_path.stat().st_size
    job = repair_jobs.get(relative_path)
    if job is not None:
        job.bytes_processed = 0
        job.total_bytes = total_bytes
        job.bytes_per_second = 0.0
        job.process = recover_proc
    tracker = asyncio.create_task(track_repair_progress(recover_proc.pid, mcap_path, relative_path, total_bytes))
    try:
        _, recover_stderr_bytes = await recover_proc.communicate()
    finally:
        tracker.cancel()
        if job is not None:
            job.process = None
    recover_stderr = recover_stderr_bytes.decode("utf-8", "ignore")
    raise_if_recover_failed(mcap_path, recover_proc.returncode, recover_stderr)

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


async def recovered_recording_bytes(mcap_path: Path) -> AsyncIterator[bytes]:
    """Yields a closed, indexed copy of a recording that may still be open or truncated."""
    recover_proc = await start_mcap_recover(mcap_path, "/dev/stdout")
    if recover_proc.stdout is None or recover_proc.stderr is None:
        raise RepairFailed("Could not read the recovered recording.")

    try:
        while True:
            chunk = await recover_proc.stdout.read(64 * 1024)
            if not chunk:
                break
            yield chunk
        recover_stderr = (await recover_proc.stderr.read()).decode("utf-8", "ignore")
        returncode = await recover_proc.wait()
    except asyncio.CancelledError:
        recover_proc.terminate()
        await recover_proc.wait()
        raise

    raise_if_recover_failed(mcap_path, returncode, recover_stderr)


async def process_recording(mcap_path: Path, relative_path: str) -> None:
    job = repair_jobs.get(relative_path)
    try:
        await recover_mcap(mcap_path, relative_path)
    except RepairFailed as failure:
        if job is not None and job.cancelled:
            logger.info(f"Repair of {relative_path} was cancelled, the recording was left as it was")
        elif job is not None:
            logger.error(f"Repair of {relative_path} failed: {failure}")
            job.error = str(failure)
        else:
            logger.error(f"Repair of {relative_path} failed: {failure}")
    finally:
        if job is not None:
            job.process = None
            if job.cancelled or job.error is None:
                repair_jobs.pop(relative_path, None)


def current_status() -> ProcessingStatus:
    processing = [
        ProcessingFile(
            name=Path(path).name,
            path=path,
            bytes_processed=job.bytes_processed,
            total_bytes=job.total_bytes,
            bytes_per_second=job.bytes_per_second,
        )
        for path, job in list(repair_jobs.items())
        if job.error is None
    ]
    return ProcessingStatus(
        processing=processing,
        failed=[
            FailedRepair(name=Path(path).name, path=path, error=job.error)
            for path, job in list(repair_jobs.items())
            if job.error is not None
        ],
    )


def _active_repair(relative_path: str) -> RepairJob | None:
    job = repair_jobs.get(relative_path)
    if job is None or job.error is not None:
        return None
    return job


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
    summary="Get MCAP repair status.",
)
@to_http_exception
async def get_processing_status() -> ProcessingStatus:
    return current_status()


@recorder_router.get(
    "/files/{filename:path}/index",
    response_model=RecordingIndex,
    summary="Walk an MCAP recording and return its chunk index.",
)
@to_http_exception
async def get_recording_index(
    filename: str,
    from_offset: int = Query(0, alias="from", ge=0),
    limit: int = Query(2000, ge=1, le=20000),
) -> RecordingIndex:
    path = resolve_recording(filename)
    try:
        return await walk_mcap_index(path, from_offset, limit)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@recorder_router.get(
    "/files/{filename:path}/download",
    response_model=None,
    summary="Download a recording. Ongoing files are recovered so the copy has an index.",
)
@to_http_exception
async def download_recording_request(filename: str) -> FileResponse | StreamingResponse:
    path = resolve_recording(filename)
    if mcap_is_indexed(path):
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")
    if not shutil.which("mcap"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The mcap tool is not available on this vehicle.",
        )
    return StreamingResponse(
        recovered_recording_bytes(path),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


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
    if _active_repair(relative_path) is not None:
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

    repair_jobs[relative_path] = RepairJob()
    task = asyncio.create_task(process_recording(path, relative_path))
    processing_tasks.add(task)
    task.add_done_callback(processing_tasks.discard)
    return current_status()


@recorder_router.delete(
    "/files/{filename:path}/repair",
    response_model=ProcessingStatus,
    summary="Stop a repair that is running, leaving the recording as it was.",
)
@to_http_exception
async def cancel_repair_request(filename: str) -> ProcessingStatus:
    path = resolve_recording(filename)
    relative_path = str(path.relative_to(ensure_recorder_dir()))
    job = _active_repair(relative_path)
    if job is None or job.process is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This recording is not being repaired.",
        )

    job.cancelled = True
    logger.info(f"Cancelling the repair of {relative_path}")
    try:
        job.process.terminate()
    except ProcessLookupError:
        # It finished while the request was on its way, so the repair reports its own outcome.
        job.cancelled = False
    return current_status()


@recorder_router.delete(
    "/files/{filename:path}",
    summary="Delete a recording.",
    status_code=status.HTTP_204_NO_CONTENT,
)
@to_http_exception
async def delete_recording(filename: str) -> None:
    path = resolve_recording(filename)
    relative_path = str(path.relative_to(ensure_recorder_dir()))
    if _active_repair(relative_path) is not None:
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


def discard_interrupted_repairs() -> None:
    """A repair killed mid-write leaves its partial copy behind, which can be as large as the recording."""
    try:
        leftovers = list(ensure_recorder_dir().glob(f"*{RECOVER_SUFFIX}"))
    except OSError as error:
        logger.warning(f"Could not look for interrupted repairs: {error}")
        return
    for leftover in leftovers:
        try:
            size = leftover.stat().st_size
            leftover.unlink()
            logger.info(f"Discarded {leftover.name} from an interrupted repair, freeing {size} bytes")
        except OSError as error:
            logger.warning(f"Could not discard {leftover.name} from an interrupted repair: {error}")


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)
    discard_interrupted_repairs()

    config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
    server = Server(config)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
