from typing import Any, List, Optional, cast

from commonwealth.utils.streaming import streamer, timeout_streamer
from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi_versioning import versioned_api_route

from extension.extension import Extension
from extension.models import ExtensionSource
from harbor import ContainerManager
from manifest import ManifestManager
from manifest.models import RepositoryEntry

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

manifest_manager = ManifestManager.instance()


@index_router_v1.get("/extensions_manifest", status_code=status.HTTP_200_OK)
async def fetch_manifest() -> list[RepositoryEntry]:
    return await manifest_manager.fetch_consolidated()


@index_router_v1.get("/installed_extensions", status_code=status.HTTP_200_OK)
async def get_installed_extensions() -> list[ExtensionSource]:
    extensions = cast(List[Extension], await Extension.from_settings())
    return [ext.source for ext in extensions]


@index_router_v1.get("/list_containers", status_code=status.HTTP_200_OK)
async def list_containers() -> Any:
    return await ContainerManager.get_running_containers()


@index_router_v1.get("/log", status_code=status.HTTP_200_OK, response_class=PlainTextResponse)
async def log_containers(container_name: str, timeout: Optional[int] = None) -> StreamingResponse:
    """
    Fetch logs of a given container.
    If timeout is provided, the stream will be closed after no log line is received for the given timeout.
    """
    stream = ContainerManager.get_container_log_by_name(container_name)

    if timeout is not None:
        return StreamingResponse(timeout_streamer(stream, timeout=timeout), media_type="text/plain")

    return StreamingResponse(streamer(stream, heartbeats=0.1), media_type="text/plain")


@index_router_v1.get("/stats", status_code=status.HTTP_200_OK)
async def load_stats() -> Any:
    return await ContainerManager.get_containers_stats()


@index_router_v1.get("/", status_code=200)
async def root() -> RedirectResponse:
    """
    Root endpoint for the Kraken API V1.
    """
    return RedirectResponse(url="/v1.0/docs")
