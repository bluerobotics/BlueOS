from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import Response
from fastapi_versioning import version

from kraken.models import ExtensionModel
# Just proxy to V2
import api.v2.routers.extension as v2_ext_api


# Creates Extension router
extension_router_v1 = APIRouter(
    prefix="/extension",
    tags=["extension"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

# Endpoints

@extension_router_v1.post("/install", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def install(extension: ExtensionModel) -> Any:
    """
    Install an extension.
    """

    return await v2_ext_api.install(extension)


@extension_router_v1.post("/uninstall", status_code=status.HTTP_200_OK)
@version(1, 0)
async def uninstall(extension_identifier: str) -> Response:
    """
    Uninstall an extension.
    """

    return await v2_ext_api.uninstall(extension_identifier)


@extension_router_v1.post("/update", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def update(extension_identifier: str, new_version: str) -> Response:
    """
    Update an extension.
    """

    return await v2_ext_api.update(extension_identifier, new_version)


@extension_router_v1.post("/enable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def enable(extension_identifier: str) -> Response:
    """
    Enable an extension.
    """

    return await v2_ext_api.enable(extension_identifier)


@extension_router_v1.post("/disable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def disable(extension_identifier: str) -> Response:
    """
    Disable an extension.
    """

    return await v2_ext_api.disable(extension_identifier)


@extension_router_v1.post("/restart", status_code=status.HTTP_202_ACCEPTED)
@version(1, 0)
async def restart(extension_identifier: str) -> Response:
    """
    Restart an extension.
    """

    return await v2_ext_api.restart(extension_identifier)
