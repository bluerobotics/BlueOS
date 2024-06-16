from functools import wraps
from typing import Any, Callable, Tuple

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from fastapi_versioning import versioned_api_route

from manifest import ManifestManager
from manifest.exceptions import (
    ManifestDataFetchFailed,
    ManifestDataParseFailed,
    ManifestInvalidURL,
    ManifestNotFound,
    ManifestOperationNotAllowed,
)
from manifest.models import (
    Manifest,
    ManifestSource,
    RepositoryEntry,
    UpdateManifestSource,
)

manifest_router_v2 = APIRouter(
    prefix="/manifest",
    tags=["manifest_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

manifest_manager = ManifestManager.instance()


def manifest_to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(endpoint)
    async def wrapper(*args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
        try:
            return await endpoint(*args, **kwargs)
        except (ManifestDataFetchFailed, ManifestDataParseFailed, ManifestInvalidURL) as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
        except ManifestNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ManifestOperationNotAllowed as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return wrapper


@manifest_router_v2.get("/", status_code=status.HTTP_200_OK)
@manifest_to_http_exception
async def fetch(data: bool = True, enabled: bool = False) -> list[Manifest]:
    """
    List all available manifests sorted by its priority. If data is set to false, only the manifest settings will be
    returned. If enabled is set to true, only enabled manifests will be returned.
    """
    return await manifest_manager.fetch(data, enabled)


@manifest_router_v2.get("/{identifier}/details", status_code=status.HTTP_200_OK)
@manifest_to_http_exception
async def fetch_by_identifier(identifier: str, data: bool = True) -> Manifest:
    """
    Get details of a given manifest. If data is set to false, only the manifest settings will be returned.
    """
    return await manifest_manager.fetch_by_identifier(identifier, data)


@manifest_router_v2.get("/consolidated", status_code=status.HTTP_200_OK)
@manifest_to_http_exception
async def fetch_consolidated() -> list[RepositoryEntry]:
    """
    List a consolidation of all repository entries from all manifest sources merged by its sorted priority, if a
    repository entry is duplicated, the one with the highest priority will be kept.
    """
    return await manifest_manager.fetch_consolidated()


@manifest_router_v2.post("/", status_code=status.HTTP_201_CREATED)
@manifest_to_http_exception
async def create(body: ManifestSource, validate_url: bool = True) -> Manifest:
    """
    Creates a new manifest source.
    """
    return await manifest_manager.add_source(body, validate_url)


@manifest_router_v2.post("/{identifier}/enable", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def enable(identifier: str) -> None:
    """
    Enables a manifest source.
    """
    await manifest_manager.enable_source(identifier)


@manifest_router_v2.post("/{identifier}/disable", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def disable(identifier: str) -> Response:
    """
    Disables a manifest source.
    """
    await manifest_manager.disable_source(identifier)


@manifest_router_v2.put("/{identifier}/details", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def update(identifier: str, body: UpdateManifestSource, validate_url: bool = True) -> None:
    """
    Updates a manifest source.
    """
    await manifest_manager.update_source(identifier, body, validate_url)


@manifest_router_v2.put("/orders", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def reorder_by_identifiers(body: list[str]) -> None:
    """
    Reorders all manifests based on the order of given list of identifiers.
    """
    await manifest_manager.order_sources(body)


@manifest_router_v2.put("/{identifier}/order/{order}", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def reorder_by_identifier(identifier: str, order: int) -> None:
    """
    Reorders a given manifest source priority.
    """
    await manifest_manager.order_source(identifier, order)


@manifest_router_v2.delete("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
@manifest_to_http_exception
async def delete(identifier: str) -> Response:
    """
    Deletes a manifest source.
    """
    await manifest_manager.remove_source(identifier)
