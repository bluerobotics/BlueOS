from fastapi import APIRouter, status
from fastapi.responses import Response
from fastapi_versioning import versioned_api_route

extension_router_v2 = APIRouter(
    prefix="/extension",
    tags=["extension_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@extension_router_v2.get("/", status_code=status.HTTP_200_OK)
async def fetch() -> Response:
    """
    List details of all installed extensions.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.get("/{identifier}/details", status_code=status.HTTP_200_OK)
async def fetch_by_identifier(_identifier: str) -> Response:
    """
    List details of all versions of a given extension.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.get("/{identifier}/{tag}/details", status_code=status.HTTP_200_OK)
async def fetch_by_identifier_and_tag(_identifier: str, _tag: str) -> Response:
    """
    List details of a given extension version.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/", status_code=status.HTTP_201_CREATED)
async def install() -> Response:
    """
    Install an extension by a custom source instead of the valid manifests, be careful with this endpoint because it
    can install incompatible extensions. Make sure to check the extension source before installing it.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/{identifier}/install", status_code=status.HTTP_201_CREATED)
async def install_by_identifier(_identifier: str) -> Response:
    """
    Install latest version of an extension by its identifier using one of the current manifests.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/{identifier}/{tag}/install", status_code=status.HTTP_201_CREATED)
async def install_by_identifier_and_tag(_identifier: str, _tag: str) -> Response:
    """
    Install a specific version of an extension by its identifier and tag using one of the current manifests.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/{identifier}/{tag}/enable", status_code=status.HTTP_200_OK)
async def enable(_identifier: str, _tag: str) -> Response:
    """
    Enables an extension by its identifier and tag, remember that this will disable the current enabled extension.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/{identifier}/disable", status_code=status.HTTP_200_OK)
async def disable(_identifier: str) -> Response:
    """
    Disables current running extension by its identifier.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.post("/{identifier}/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart(_identifier: str) -> Response:
    """
    Restart current running extension by its identifier.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.put("/{identifier}", status_code=status.HTTP_201_CREATED)
async def update_to_latest(_identifier: str, _purge: bool = True, _stable: bool = True) -> Response:
    """
    Update a given extension by its identifier to latest (stable or not) version on the higher priority manifest and
    by default purge all other tags, if purge is set to false it will keep all other versions disabled only.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.put("/{identifier}/{tag}", status_code=status.HTTP_201_CREATED)
async def update_to_tag(_identifier: str, _tag: str, _purge: bool = True) -> Response:
    """
    Update a given extension by its identifier and tag to latest version on the higher priority manifest and by default
    purge all other tags, if purge is set to false it will keep all other versions disabled only.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.delete("/{identifier}", status_code=status.HTTP_200_OK)
async def uninstall(_identifier: str) -> Response:
    """
    Uninstall all versions of an extension by its identifier.
    """
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@extension_router_v2.delete("/{identifier}/{tag}", status_code=status.HTTP_200_OK)
async def uninstall_version(_identifier: str, _tag: str) -> Response:
    """
    Uninstall a specific version of an extension by its identifier and tag.
    """

    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
