from fastapi import APIRouter, status
from fastapi.responses import Response
from fastapi_versioning import versioned_api_route

manifest_router_v2 = APIRouter(
    prefix="/manifest",
    tags=["manifest_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

@manifest_router_v2.get("/", status_code=status.HTTP_200_OK)
async def fetch(_data: bool = True) -> Response:
    """
    List all available manifests sorted by its priority. If data is set to false, only the manifest settings will be
    returned.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.get("/{identifier}/details", status_code=status.HTTP_200_OK)
async def fetch_by_identifier(_identifier: str, _data: bool = True) -> Response:
    """
    Get details of a given manifest. If data is set to false, only the manifest settings will be returned.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.post("/", status_code=status.HTTP_201_CREATED)
async def create() -> Response:
    """
    Creates a new manifest source.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.post("/{identifier}/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable(_identifier: str) -> Response:
    """
    Enables a manifest source.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.post("/{identifier}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable(_identifier: str) -> Response:
    """
    Disables a manifest source.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.put("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
async def update(_identifier: str) -> Response:
    """
    Updates a manifest source.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.put("/{identifier}/order/{order}", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_by_identifier(_identifier: str, _order: int) -> Response:
    """
    Reorders a given manifest source priority.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@manifest_router_v2.delete("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(_identifier: str) -> Response:
    """
    Deletes a manifest source.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
