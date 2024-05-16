from typing import Any, Iterable

from commonwealth.utils.streaming import timeout_streamer
from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi_versioning import versioned_api_route

from api.v1.models import Extension
from kraken import kraken_instance

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

@index_router_v1.get("/extensions_manifest", status_code=status.HTTP_200_OK)
async def fetch_manifest() -> Any:
    return await kraken_instance.fetch_manifest()


@index_router_v1.get("/installed_extensions", status_code=status.HTTP_200_OK)
async def get_installed_extensions() -> Any:
    extensions = await kraken_instance.get_configured_extensions()
    extensions_list = [
        Extension(
            identifier=extension.identifier,
            name=extension.name,
            docker=extension.docker,
            tag=extension.tag,
            permissions=extension.permissions,
            enabled=extension.enabled,
            user_permissions=extension.user_permissions,
        )
        for extension in extensions
    ]
    extensions_list.sort(key=lambda extension: extension.name)
    return extensions_list


@index_router_v1.get("/list_containers", status_code=status.HTTP_200_OK)
async def list_containers() -> Any:
    containers = await kraken_instance.list_containers()
    return [
        {
            "name": container["Names"][0],
            "image": container["Image"],
            "imageId": container["ImageID"],
            "status": container["Status"],
        }
        for container in containers
    ]


@index_router_v1.get("/log", status_code=status.HTTP_200_OK, response_class=PlainTextResponse)
async def log_containers(container_name: str) -> Iterable[bytes]:
    return StreamingResponse(timeout_streamer(kraken_instance.stream_logs(container_name)), media_type="text/plain")  # type: ignore


@index_router_v1.get("/stats", status_code=status.HTTP_200_OK)
async def load_stats() -> Any:
    return await kraken_instance.load_stats()


@index_router_v1.get("/", status_code=200)
async def root() -> RedirectResponse:
    """
    Root endpoint for the Kraken API V1.
    """

    return RedirectResponse(url="/v1.0/docs")
