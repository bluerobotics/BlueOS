from fastapi import APIRouter, status
from fastapi_versioning import version

from kraken import Kraken
from kraken.models import ContainerModel, ContainerUsageModel


# Creates Extension router
container_router_v2 = APIRouter(
    prefix="/container",
    tags=["container"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

# Endpoints

@container_router_v2.get("/", status_code=status.HTTP_200_OK, response_model=list[ContainerModel])
@version(2, 0)
async def list() -> list[ContainerModel]:
    """
    List all running containers.
    """

    containers = await Kraken.list_containers()
    return [
        ContainerModel(
            name=container["Names"][0],
            image=container["Image"],
            image_id=container["ImageID"],
            status=container["Status"],
        )
        for container in containers
    ]


@container_router_v2.get("/stats", status_code=status.HTTP_200_OK, response_model=dict[str, ContainerUsageModel])
@version(2, 0)
async def stats() -> dict[str, ContainerUsageModel]:
    """
    List stats of all running containers.
    """

    stats = await Kraken.stats()

    return {
        key: ContainerUsageModel(
            cpu=usage[0],
            memory=usage[1],
            disk=usage[2],
        )
        for key, usage in stats.items()
    }
