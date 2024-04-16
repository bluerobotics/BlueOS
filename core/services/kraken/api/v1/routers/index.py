from typing import Any, Iterable

from fastapi import APIRouter, status
from fastapi.responses import Response, HTMLResponse, PlainTextResponse
from fastapi_versioning import version

# Just proxy to V2
import api.v2.routers.index as v2_index_api
import api.v2.routers.container as v2_container_api
import api.v2.routers.extension as v2_ext_api


# Creates Root Kraken router
index_router_v1 = APIRouter(
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

# Endpoints

@index_router_v1.get("/extensions_manifest", status_code=status.HTTP_200_OK)
@version(1, 0)
async def fetch_manifest() -> Any:
    """
    Fetch the manifest of all extensions.
    """

    return await v2_ext_api.manifest()


@index_router_v1.get("/installed_extensions", status_code=status.HTTP_200_OK)
@version(1, 0)
async def get_installed_extensions() -> Any:
    """
    List all installed extensions, sorted by name.
    """

    return await v2_ext_api.list()


@index_router_v1.get("/list_containers", status_code=status.HTTP_200_OK)
@version(1, 0)
async def list_containers() -> Any:
    """
    List all containers.
    """

    return await v2_container_api.list()


@index_router_v1.get("/log", status_code=status.HTTP_200_OK, response_class=PlainTextResponse)
@version(1, 0)
async def log_containers(container_name: str) -> Iterable[bytes]:
    """
    Get logs of a container.
    """

    return await v2_index_api.log(container_name)


@index_router_v1.get("/stats", status_code=status.HTTP_200_OK)
@version(1, 0)
async def load_stats() -> Any:
    """
    List all containers.
    """

    return await v2_container_api.stats()


@index_router_v1.get("/", response_class=HTMLResponse, status_code=200)
@version(1, 0)
async def root() -> Response:
    html_content = """
    <html>
        <head>
            <title>Kraken</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
