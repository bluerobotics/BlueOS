from typing import Any

import aiodocker
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi_versioning import versioned_api_route
from pydantic import BaseModel

from utils.chooser import VersionChooser

version_router_v1 = APIRouter(
    prefix="/version",
    tags=["version_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class DockerImageIdentifier(BaseModel):
    repository: str
    tag: str


async def get_docker_client():
    async with aiodocker.Docker() as docker_client:
        yield VersionChooser(docker_client)


@version_router_v1.get(
    "/current", summary="Return the current running version of BlueOS", status_code=status.HTTP_200_OK
)
async def get_version(version_chooser: VersionChooser = Depends(get_docker_client)) -> Any:
    return await version_chooser.get_version()


@version_router_v1.post("/current", summary="Sets the current version of BlueOS to a new tag")
async def set_version(
    request: DockerImageIdentifier, version_chooser: VersionChooser = Depends(get_docker_client)
) -> Any:
    return await version_chooser.set_version(request.repository, request.tag)


@version_router_v1.post("/pull", summary="Pulls a version from dockerhub")
async def pull_version(
    request: DockerImageIdentifier, version_chooser: VersionChooser = Depends(get_docker_client)
) -> Any:
    return await version_chooser.pull_version(request.repository, request.tag)


@version_router_v1.delete("/delete", summary="Delete the selected version of BlueOS")
async def delete_version(
    request: DockerImageIdentifier, version_chooser: VersionChooser = Depends(get_docker_client)
) -> Any:
    return await version_chooser.delete_version(request.repository, request.tag)


@version_router_v1.get("/available/local", summary="Returns available local versions")
async def get_available_local_versions(version_chooser: VersionChooser = Depends(get_docker_client)) -> Any:
    return await version_chooser.get_available_local_versions()


@version_router_v1.get(
    "/available/{repository}/{image}", summary="Returns available versions, both locally and in dockerhub"
)
async def get_available_versions(
    repository: str, image: str, version_chooser: VersionChooser = Depends(get_docker_client)
) -> Any:
    return await version_chooser.get_available_versions(f"{repository}/{image}")


@version_router_v1.post("/load", summary="Load a docker tar file")
async def load(file: UploadFile = File(...), version_chooser: VersionChooser = Depends(get_docker_client)) -> Any:
    data = await file.read()
    return await version_chooser.load(data)


@version_router_v1.post("/restart", summary="Restart the currently running docker container")
async def restart(version_chooser: VersionChooser = Depends(get_docker_client)) -> Any:
    return await version_chooser.restart()
