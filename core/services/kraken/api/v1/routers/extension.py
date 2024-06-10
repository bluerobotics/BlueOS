import asyncio
from typing import Any, List, cast

from commonwealth.utils.streaming import streamer
from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from fastapi_versioning import versioned_api_route

from api.v2.routers.extension import extension_to_http_exception
from extension.extension import Extension
from extension.models import ExtensionSource

extension_router_v1 = APIRouter(
    prefix="/extension",
    tags=["extension_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@extension_router_v1.post("/install", status_code=status.HTTP_201_CREATED)
@extension_to_http_exception
async def install_extension(body: ExtensionSource) -> StreamingResponse:
    extension = Extension(body)
    return StreamingResponse(streamer(extension.install(atomic=True)))


@extension_router_v1.post("/uninstall", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def uninstall_extension(extension_identifier: str) -> Any:
    extensions = cast(List[Extension], await Extension.from_settings(extension_identifier))
    await asyncio.gather(*[ext.uninstall() for ext in extensions])


@extension_router_v1.post("/update_to_version", status_code=status.HTTP_201_CREATED)
@extension_to_http_exception
async def update_extension(extension_identifier: str, new_version: str) -> StreamingResponse:
    extension = cast(Extension, await Extension.from_manifest(extension_identifier, new_version))
    return StreamingResponse(streamer(extension.update(True)))


@extension_router_v1.post("/enable", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def enable_extension(extension_identifier: str) -> Any:
    extension = cast(List[Extension], await Extension.from_settings(extension_identifier))
    await extension[0].enable()


@extension_router_v1.post("/disable", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def disable_extension(extension_identifier: str) -> Any:
    extension: Extension = await Extension.from_running(extension_identifier)
    await extension.disable()


@extension_router_v1.post("/restart", status_code=status.HTTP_202_ACCEPTED)
@extension_to_http_exception
async def restart_extension(extension_identifier: str) -> Any:
    extension: Extension = await Extension.from_running(extension_identifier)
    await extension.restart()
