from typing import Any, AsyncGenerator

import aiodocker
from fastapi import APIRouter, Depends, status
from fastapi_versioning import versioned_api_route
from pydantic import BaseModel

from utils.chooser import VersionChooser

bootstrap_router_v1 = APIRouter(
    prefix="/bootstrap",
    tags=["bootstrap_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class BootstrapRequest(BaseModel):
    tag: str


async def get_docker_client() -> AsyncGenerator[VersionChooser, None]:
    async with aiodocker.Docker() as docker_client:
        yield VersionChooser(docker_client)


@bootstrap_router_v1.get("/current", summary="Return the current running version of BlueOS-bootstrap")
async def get_bootstrap_version(version_chooser: VersionChooser = Depends(get_docker_client)) -> Any:
    return await version_chooser.get_bootstrap_version()


@bootstrap_router_v1.post("/current", summary="Sets the current version of BlueOS-bootstrap to a new tag")
async def set_bootstrap_version(
    request: BootstrapRequest, version_chooser: VersionChooser = Depends(get_docker_client)
) -> Any:
    return await version_chooser.set_bootstrap_version(request.tag)
