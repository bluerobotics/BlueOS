import asyncio
from functools import wraps
from typing import Any, Callable, List, Tuple, cast

from commonwealth.utils.streaming import streamer
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from fastapi_versioning import versioned_api_route

from extension.exceptions import (
    ExtensionInsufficientStorage,
    ExtensionNotFound,
    ExtensionNotRunning,
)
from extension.extension import Extension
from extension.models import ExtensionSource

extension_router_v2 = APIRouter(
    prefix="/extension",
    tags=["extension_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def extension_to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(endpoint)
    async def wrapper(*args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
        try:
            return await endpoint(*args, **kwargs)
        except ExtensionNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ExtensionNotRunning as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        except ExtensionInsufficientStorage as error:
            raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=str(error)) from error
        except HTTPException as error:
            raise error
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return wrapper


@extension_router_v2.get("/", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def fetch() -> list[ExtensionSource]:
    """
    List details of all installed extensions.
    """
    extensions = cast(List[Extension], await Extension.from_settings())
    return [ext.source for ext in extensions]


@extension_router_v2.get("/{identifier}/details", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def fetch_by_identifier(identifier: str) -> list[ExtensionSource]:
    """
    List details of all versions of a given extension.
    """
    extensions = cast(List[Extension], await Extension.from_settings(identifier))
    return [ext.source for ext in extensions]


@extension_router_v2.get("/{identifier}/{tag}/details", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def fetch_by_identifier_and_tag(identifier: str, tag: str) -> ExtensionSource:
    """
    List details of a given extension version.
    """
    extension = cast(Extension, await Extension.from_settings(identifier, tag))
    return extension.source


@extension_router_v2.post("/", status_code=status.HTTP_201_CREATED)
@extension_to_http_exception
async def install(body: ExtensionSource) -> StreamingResponse:
    """
    Install an extension by a custom source instead of the valid manifests, be careful with this endpoint because it
    can install incompatible extensions. Make sure to check the extension source before installing it.
    """
    extension = Extension(body)
    return StreamingResponse(streamer(extension.install(atomic=True)))


@extension_router_v2.post("/{identifier}/install", status_code=status.HTTP_201_CREATED)
@extension_to_http_exception
async def install_by_identifier(identifier: str, stable: bool = True) -> StreamingResponse:
    """
    Install latest version of an extension by its identifier using one of the current manifests.
    """
    extension: Extension = await Extension.from_latest(identifier, stable)
    return StreamingResponse(streamer(extension.install()))


@extension_router_v2.post("/{identifier}/{tag}/install", status_code=status.HTTP_201_CREATED)
@extension_to_http_exception
async def install_by_identifier_and_tag(identifier: str, tag: str) -> StreamingResponse:
    """
    Install a specific version of an extension by its identifier and tag using one of the current manifests.
    """
    extension = cast(Extension, await Extension.from_manifest(identifier, tag))
    return StreamingResponse(streamer(extension.install()))


@extension_router_v2.post("/{identifier}/{tag}/enable", status_code=status.HTTP_204_NO_CONTENT)
@extension_to_http_exception
async def enable(identifier: str, tag: str) -> None:
    """
    Enables an extension by its identifier and tag, remember that this will disable the current enabled extension.
    """
    extension = cast(Extension, await Extension.from_settings(identifier, tag))
    await extension.enable()


@extension_router_v2.post("/{identifier}/disable", status_code=status.HTTP_204_NO_CONTENT)
@extension_to_http_exception
async def disable(identifier: str) -> None:
    """
    Disables current running extension by its identifier.
    """
    extension = await Extension.from_running(identifier)
    await extension.disable()


@extension_router_v2.post("/{identifier}/restart", status_code=status.HTTP_202_ACCEPTED)
@extension_to_http_exception
async def restart(identifier: str) -> None:
    """
    Restart current running extension by its identifier.
    """
    extension = await Extension.from_running(identifier)
    await extension.restart()


@extension_router_v2.put("/{identifier}", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def update_to_latest(identifier: str, purge: bool = True, stable: bool = True) -> StreamingResponse:
    """
    Update a given extension by its identifier to latest (stable or not) version on the higher priority manifest and
    by default purge all other tags, if purge is set to false it will keep all other versions disabled only.
    """
    extension = await Extension.from_latest(identifier, stable)
    return StreamingResponse(streamer(extension.update(purge)))


@extension_router_v2.put("/{identifier}/{tag}", status_code=status.HTTP_200_OK)
@extension_to_http_exception
async def update_to_tag(identifier: str, tag: str, purge: bool = True) -> Response:
    """
    Update a given extension by its identifier and tag to latest version on the higher priority manifest and by default
    purge all other tags, if purge is set to false it will keep all other versions disabled only.
    """
    extension = cast(Extension, await Extension.from_manifest(identifier, tag))
    return StreamingResponse(streamer(extension.update(purge)))


@extension_router_v2.delete("/{identifier}", status_code=status.HTTP_202_ACCEPTED)
@extension_to_http_exception
async def uninstall(identifier: str) -> None:
    """
    Uninstall all versions of an extension by its identifier.
    """
    extensions = cast(List[Extension], await Extension.from_settings(identifier))
    await asyncio.gather(*[ext.uninstall() for ext in extensions])


@extension_router_v2.delete("/{identifier}/{tag}", status_code=status.HTTP_202_ACCEPTED)
@extension_to_http_exception
async def uninstall_version(identifier: str, tag: str) -> None:
    """
    Uninstall a specific version of an extension by its identifier and tag.
    """
    extension = cast(Extension, await Extension.from_settings(identifier, tag))
    await extension.uninstall()
