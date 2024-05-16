from typing import Any

from commonwealth.utils.streaming import streamer
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi_versioning import versioned_api_route

from api.v1.models import Extension
from kraken import kraken_instance

extension_router_v1 = APIRouter(
    prefix="/extension",
    tags=["extension_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@extension_router_v1.post("/install", status_code=status.HTTP_201_CREATED)
async def install_extension(extension: Extension) -> Any:
    if not extension.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid extension description",
        )
    if not kraken_instance.has_enough_disk_space():
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough disk space to install the extension",
        )
    compatible_digest = await kraken_instance.is_compatible_extension(extension.identifier, extension.tag)
    # Throw an exception only if compatible_digest is False, indicating the extension is in the manifest but it is
    # incompatible. If compatible_digest is None, we are going to trusty that the image is compatible and will work
    if compatible_digest is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension is not compatible with the current machine running BlueOS.",
        )
    return StreamingResponse(streamer(kraken_instance.install_extension(extension, compatible_digest)))


@extension_router_v1.post("/uninstall", status_code=status.HTTP_200_OK)
async def uninstall_extension(extension_identifier: str) -> Any:
    return await kraken_instance.uninstall_extension_from_identifier(extension_identifier)


@extension_router_v1.post("/update_to_version", status_code=status.HTTP_201_CREATED)
async def update_extension(extension_identifier: str, new_version: str) -> Any:
    return StreamingResponse(streamer(kraken_instance.update_extension_to_version(extension_identifier, new_version)))


@extension_router_v1.post("/enable", status_code=status.HTTP_200_OK)
async def enable_extension(extension_identifier: str) -> Any:
    return await kraken_instance.enable_extension(extension_identifier)


@extension_router_v1.post("/disable", status_code=status.HTTP_200_OK)
async def disable_extension(extension_identifier: str) -> Any:
    return await kraken_instance.disable_extension(extension_identifier)


@extension_router_v1.post("/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_extension(extension_identifier: str) -> Any:
    return await kraken_instance.restart_extension(extension_identifier)
