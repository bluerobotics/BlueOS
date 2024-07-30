from functools import wraps
from typing import Any, Callable, Optional, Tuple

from commonwealth.utils.streaming import streamer, timeout_streamer
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi_versioning import versioned_api_route

from harbor import ContainerManager
from harbor.exceptions import ContainerNotFound
from harbor.models import ContainerModel, ContainerUsageModel

container_router_v2 = APIRouter(
    prefix="/container",
    tags=["container_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def container_to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(endpoint)
    async def wrapper(*args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
        try:
            return await endpoint(*args, **kwargs)
        except ContainerNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return wrapper


@container_router_v2.get("/", status_code=status.HTTP_200_OK)
@container_to_http_exception
async def list_container() -> list[ContainerModel]:
    """
    List details all running containers.
    """
    return await ContainerManager.get_running_containers()


@container_router_v2.get("/{container_name}/details", status_code=status.HTTP_200_OK)
@container_to_http_exception
async def fetch_container(container_name: str) -> ContainerModel:
    """
    List details of a given container.
    """
    return await ContainerManager.get_running_container_by_name(container_name)


@container_router_v2.get("/{container_name}/log", status_code=status.HTTP_200_OK)
@container_to_http_exception
async def fetch_log_by_container_name(container_name: str, timeout: Optional[int] = None) -> StreamingResponse:
    """
    Fetch logs of a given container.
    If timeout is provided, the stream will be closed after no log line is received for the given timeout.
    """
    stream = ContainerManager.get_container_log_by_name(container_name)

    if timeout is not None:
        return StreamingResponse(timeout_streamer(stream, timeout=timeout), media_type="text/plain")

    return StreamingResponse(streamer(stream, heartbeats=0.1), media_type="text/plain")


@container_router_v2.get("/stats", status_code=status.HTTP_200_OK)
@container_to_http_exception
async def list_stats() -> dict[str, ContainerUsageModel]:
    """
    List stats of all running containers.
    """
    return await ContainerManager.get_containers_stats()


@container_router_v2.get("/{container_name}/stats", status_code=status.HTTP_200_OK)
@container_to_http_exception
async def fetch_stats_by_container_name(container_name: str) -> ContainerUsageModel:
    """
    List stats of a given running containers.
    """
    return await ContainerManager.get_container_stats_by_name(container_name)
