#! /usr/bin/env python3

import asyncio
import contextlib
import logging
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List

from urllib.parse import quote

from aiocache import cached
from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.general import file_is_open_async
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

SERVICE_NAME = "recorder-extractor"
RECORDER_DIR = Path("/usr/blueos/userdata/recorder")
PORT = 9150

# Prevent thumbnails from being generated while MCAP extraction is running
thumbnail_lock = asyncio.Lock()

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Recorder Extractor service")


class RecordingFile(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified: float
    download_url: str
    stream_url: str
    thumbnail_url: str


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
    if candidate.suffix.lower() != ".mp4":
        logger.warning(f"Rejected non-mp4 path: {candidate}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .mp4 recordings are supported.")
    if not candidate.exists() or not candidate.is_file():
        logger.warning(f"Recording not found: {candidate}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found.")
    return candidate


def parse_duration_ns(discover_output: str) -> int:
    duration_ns = 0
    for line in discover_output.splitlines():
        # Example: Duration: 0:00:12.345678000
        if "Duration:" not in line:
            continue

        try:
            parts = line.split("Duration:", maxsplit=1)[1].strip().split(".")
            hms = parts[0]
            nanos = parts[1] if len(parts) > 1 else "0"
            hours, minutes, seconds = [int(x) for x in hms.split(":")]
            duration_ns = ((hours * 3600) + (minutes * 60) + seconds) * 1_000_000_000 + int(nanos)
            break
        except Exception as exception:
            logger.error(f"Failed to parse duration: {exception}")
            break
    return duration_ns


@cached()
async def build_thumbnail_bytes(path: Path) -> bytes:
    """
    Extract a single JPEG frame from the recording using a raw gst-launch pipeline (ASYNC).

    Seek to the middle of the file, scale to 320x180, and encode as JPEG. If any step fails,
    propagate an HTTP 500 so callers can fall back.
    """
    # 1) Discover duration (nanoseconds) using gst-discoverer
    discover_cmd = ["gst-discoverer-1.0", f"file://{path}"]
    discover_proc = await asyncio.create_subprocess_exec(
        *discover_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    stdout_bytes, stderr_bytes = await discover_proc.communicate()
    stdout = stdout_bytes.decode("utf-8", "ignore")
    stderr = stderr_bytes.decode("utf-8", "ignore")
    if discover_proc.returncode != 0:
        logger.error(f"gst-discoverer-1.0 failed for {path}: {stderr.strip()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to inspect recording.",
        )

    duration_ns = parse_duration_ns(stdout)
    target_ns = duration_ns // 2 if duration_ns > 0 else 0
    target_sec = target_ns / 1_000_000_000

    # 2) Grab a frame at the target time using gst-play-1.0 + raw pipeline sink
    pipeline = (
        "videoconvert ! videoscale ! "
        "video/x-raw,width=320,height=180 ! "
        "jpegenc snapshot=true quality=85 ! "
        "fdsink fd=1 sync=false"
    )

    play_cmd = [
        "gst-play-1.0",
        f"--start-position={target_sec:.3f}",
        f"--videosink={pipeline}",
        "--audiosink=fakesink",
        "--no-interactive",
        "-q",
        f"file://{path}",
    ]
    logger.info(
        f"Thumbnail target: duration_ns={duration_ns} target_ns={target_ns} target_sec={target_sec:.3f} file={path}"
    )
    logger.info(f"Thumbnail command: {' '.join(play_cmd)}")
    play_proc = await asyncio.create_subprocess_exec(
        *play_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    stdout_bytes, stderr_bytes = await play_proc.communicate()
    stderr = stderr_bytes.decode("utf-8", "ignore")
    if play_proc.returncode != 0 or not stdout:
        logger.error(f"gst-play-1.0 failed for {path} (code={play_proc.returncode}): {stderr}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate thumbnail.",
        )

    return stdout_bytes


async def extract_mcap_recordings() -> None:
    """Periodically extract MP4 files from MCAP recordings."""
    while True:
        await asyncio.sleep(10)
        try:
            base = ensure_recorder_dir()
            for mcap_path in base.rglob("*.mcap"):
                # If the folder already exists, it's already extracted or deleted by user
                output_dir = mcap_path.with_suffix("")
                if output_dir.exists():
                    continue

                logger.info(f"Checking if file is in use: {mcap_path}")
                if await file_is_open_async(mcap_path):
                    logger.info(f"Skipping MCAP extract, file in use: {mcap_path}")
                    continue

                command = [
                    "mcap-foxglove-video-extract",
                    str(mcap_path),
                    "all",
                    "--output",
                    str(output_dir),
                ]
                logger.info(f"Extracting MCAP video to {output_dir} with command: {' '.join(command)}")
                async with thumbnail_lock:
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        text=False,
                    )
                    stdout_bytes, stderr_bytes = await process.communicate()
                    stdout = stdout_bytes.decode("utf-8", "ignore")
                    stderr = stderr_bytes.decode("utf-8", "ignore")
                if process.returncode != 0:
                    logger.error(
                        f"MCAP extract failed for {mcap_path} (code={process.returncode}): {stderr}",
                    )
                else:
                    logger.info(f"MCAP extract completed for {mcap_path}: {stdout.strip()}")
        except Exception as exception:
            logger.exception(f"MCAP extraction loop failed: {exception}")


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
    prefix="/recorder",
    tags=["recorder_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@recorder_router.get(
    "/files",
    response_model=List[RecordingFile],
    summary="List available MP4 recordings under /usr/blueos/userdata/recorder.",
)
@to_http_exception
async def list_recordings() -> List[RecordingFile]:
    base_url = "/recorder-extractor/v1.0/recorder/files"
    files: List[RecordingFile] = []
    base_path = ensure_recorder_dir()
    mp4_files = sorted(base_path.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in mp4_files:
        stat = path.stat()
        relative_path = path.relative_to(base_path)
        safe_path = str(relative_path)
        encoded_path = quote(safe_path, safe="")
        files.append(
            RecordingFile(
                name=path.name,
                path=safe_path,
                size_bytes=stat.st_size,
                modified=stat.st_mtime,
                download_url=f"{base_url}/{encoded_path}",
                stream_url=f"{base_url}/{encoded_path}",
                thumbnail_url=f"{base_url}/{encoded_path}/thumbnail",
            )
        )
    return files


@recorder_router.get(
    "/files/{filename:path}/thumbnail",
    summary="Grab a thumbnail from a recording.",
)
@to_http_exception
async def get_recording_thumbnail(filename: str) -> StreamingResponse:
    path = resolve_recording(filename)
    async with thumbnail_lock:
        thumbnail_bytes = await build_thumbnail_bytes(path)
    return StreamingResponse(BytesIO(thumbnail_bytes), media_type="image/jpeg")


@recorder_router.delete(
    "/files/{filename:path}",
    summary="Delete a recording.",
    status_code=status.HTTP_204_NO_CONTENT,
)
@to_http_exception
async def delete_recording(filename: str) -> None:
    path = resolve_recording(filename)
    try:
        path.unlink()
    except Exception as exception:
        logger.exception(f"Failed to delete recording {filename}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete recording.",
        ) from exception


@recorder_router.get(
    "/files/{filename:path}",
    summary="Download or stream a recording.",
)
@to_http_exception
async def get_recording(filename: str) -> FileResponse:
    path = resolve_recording(filename)
    return FileResponse(path, media_type="video/mp4", filename=path.name)


fast_api_app = FastAPI(
    title="Recorder Extractor API",
    description="Serve recorded MP4 files for playback and download.",
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
    extractor_task = asyncio.create_task(extract_mcap_recordings())
    try:
        await init_sentry_async(SERVICE_NAME)

        config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
        server = Server(config)

        await server.serve()
    finally:
        extractor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await extractor_task


if __name__ == "__main__":
    asyncio.run(main())
