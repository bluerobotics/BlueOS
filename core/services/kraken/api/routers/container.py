# FastAPI
from fastapi import APIRouter, status
from fastapi.responses import Response
# Versioning
from fastapi_versioning import version
# Kraken
from kraken import Kraken

# Creates Extension router
container_router = APIRouter(
    prefix="/container",
    tags=["container"],
    responses={
        404: {"description": "Not found"}
    },
)

# Endpoints

@container_router.get("/", status_code=status.HTTP_200_OK)
@version(1, 0)
async def list() -> Response:
    containers = await Kraken.list_containers()
    return [
        {
            "name": container["Names"][0],
            "image": container["Image"],
            "imageId": container["ImageID"],
            "status": container["Status"],
        }
        for container in containers
    ]


@container_router.get("/stats", status_code=status.HTTP_200_OK)
@version(1, 0)
async def stats() -> Response:
    return await Kraken.stats()
