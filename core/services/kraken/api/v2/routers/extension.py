from fastapi import APIRouter, status, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi_versioning import version

from kraken import Extension, Kraken
from kraken.exceptions import ExtensionContainerNotFound, ExtensionNotFound
from kraken.models import ExtensionModel


# Creates Extension router
extension_router_v2 = APIRouter(
    prefix="/extension",
    tags=["extension"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

# Common

def handle_extension_exceptions(error: Exception) -> None:
    """
    Handle exceptions raised by the Extension class.

    Args:
        error (Exception): The exception to handle.
    """

    if isinstance(error, (ExtensionNotFound, ExtensionContainerNotFound)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        )

# Endpoints

@extension_router_v2.get("/", status_code=status.HTTP_200_OK, response_model=list[ExtensionModel])
@version(2, 0)
async def list() -> list[ExtensionModel]:
    """
    List all installed extensions, sorted by name.
    """

    extensions = await Kraken.installed_extensions()
    extensions.sort(key=lambda x: x.name)

    return [
        ExtensionModel(
            identifier=ext.identifier,
            name=ext.name,
            docker=ext.docker,
            tag=ext.tag,
            permissions=ext.permissions,
            enabled=ext.enabled,
            user_permissions=ext.user_permissions,
        )
        for ext in extensions
    ]


@extension_router_v2.post("/install", status_code=status.HTTP_201_CREATED, response_class=StreamingResponse)
@version(2, 0)
async def install(identifier: str, tag: str | None = None) -> StreamingResponse:
    """
    Install an extension by its identifier and tag, if not tag is provided, the latest tag in manifest will be used.
    """

    if not tag:
        tag = await Extension.latest_tag(identifier)

    ext = await Extension.from_compatible_image(identifier, tag)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension is not compatible with the current machine running BlueOS.",
        )
    if not Kraken.has_enough_disk_space(ext.image.expanded_size):
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough disk space to install the extension",
        )

    return StreamingResponse(ext.install())


@extension_router_v2.post("/uninstall", status_code=status.HTTP_200_OK)
@version(2, 0)
async def uninstall(identifier: str, tag: str | None = None) -> Response:
    """
    Uninstall an extension by its identifier and tag, if not tag is provided, the latest tag installed will be used.
    """

    if not tag:
        tag = await Extension.latest_installed_tag(identifier)

    ext = Extension(identifier, tag)
    try:
        return await ext.uninstall()
    except Exception as error:
        handle_extension_exceptions(error)


@extension_router_v2.post("/update", status_code=status.HTTP_201_CREATED)
@version(2, 0)
async def update(identifier: str, tag: str | None = None) -> StreamingResponse:
    """
    Update an extension by its identifier and tag, if not tag is provided, the latest tag will in manifest be used.
    """

    if not tag:
        tag = await Extension.latest_tag(identifier)

    ext = await Extension.from_compatible_image(identifier, tag)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension is not compatible with the current machine running BlueOS.",
        )
    if not Kraken.has_enough_disk_space(ext.image.expanded_size):
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough disk space to install the extension",
        )

    return StreamingResponse(ext.update())


@extension_router_v2.post("/enable", status_code=status.HTTP_200_OK)
@version(2, 0)
async def enable(identifier: str, tag: str | None = None) -> Response:
    """
    Enable an extension by its identifier and tag, if not tag is provided, the latest tag installed will be used.
    """

    if not tag:
        tag = await Extension.latest_installed_tag(identifier)

    ext = Extension(identifier, tag)
    try:
        return await ext.enable()
    except Exception as error:
        handle_extension_exceptions(error)


@extension_router_v2.post("/disable", status_code=status.HTTP_200_OK)
@version(2, 0)
async def disable(identifier: str, tag: str | None = None) -> Response:
    """
    Disable an extension by its identifier and tag, if not tag is provided, the latest tag installed will be used.
    """

    if not tag:
        tag = await Extension.latest_installed_tag(identifier)

    ext = Extension(identifier, tag)
    try:
        return await ext.disable()
    except Exception as error:
        handle_extension_exceptions(error)


@extension_router_v2.post("/restart", status_code=status.HTTP_202_ACCEPTED)
@version(2, 0)
async def restart(identifier: str, tag: str | None = None) -> Response:
    """
    Restart an extension by its identifier and tag, if not tag is provided, the latest tag installed will be used.
    """

    if not tag:
        tag = await Extension.latest_installed_tag(identifier)

    ext = Extension(identifier, tag)
    try:
        return await ext.restart()
    except Exception as error:
        handle_extension_exceptions(error)
