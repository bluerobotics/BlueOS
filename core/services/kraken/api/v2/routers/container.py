from fastapi import APIRouter, status
from fastapi.responses import Response
from fastapi_versioning import versioned_api_route

container_router_v2 = APIRouter(
    prefix="/container",
    tags=["container_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@container_router_v2.get("/", status_code=status.HTTP_200_OK)
async def list_container() -> Response:
    """
    List details all running containers.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@container_router_v2.get("/{container_name}/details", status_code=status.HTTP_200_OK)
async def fetch_container(_container_name: str) -> Response:
    """
    List details of a given container.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@container_router_v2.get("/log", status_code=status.HTTP_200_OK)
async def list_log() -> Response:
    """
    List logs all running containers.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@container_router_v2.get("/{container_name}/log", status_code=status.HTTP_200_OK)
async def fetch_log_by_container_name(_container_name: str) -> Response:
    """
    Get logs of a given container.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@container_router_v2.get("/stats", status_code=status.HTTP_200_OK)
async def list_stats() -> Response:
    """
    List stats of all running containers.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@container_router_v2.get("/{container_name}/stats", status_code=status.HTTP_200_OK)
async def fetch_stats_by_container_name(_container_name: str) -> Response:
    """
    List stats of a given running containers.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
