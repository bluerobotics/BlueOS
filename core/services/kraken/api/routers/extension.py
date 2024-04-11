# FastAPI
from fastapi import APIRouter, status, HTTPException
from fastapi.responses import Response, StreamingResponse
# Versioning
from fastapi_versioning import version
# Kraken
from kraken import Kraken
from kraken.extension import Extension

# Creates Extension router
extension_router = APIRouter(
    prefix="/extension",
    tags=["extension"],
    responses={
        404: {"description": "Not found"}
    },
)

# Endpoints

@extension_router.get("/", status_code=status.HTTP_200_OK)
@version(1, 0)
async def list() -> Response:
    extensions = await Kraken.installed_extensions()
    extensions.sort(key=lambda x: x.name)

    return [ extension.as_dict() for extension in extensions ]


@extension_router.get("/manifest", status_code=status.HTTP_200_OK)
@version(1, 0)
async def manifest() -> Response:
    return await Kraken.fetch_manifest()


@extension_router.post("/install", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def install(identifier: str, tag: str) -> Response:
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


@extension_router.post("/uninstall", status_code=status.HTTP_200_OK)
@version(1, 0)
async def uninstall(identifier: str, tag: str) -> Response:
    ext = Extension(identifier, tag)
    return await ext.uninstall()


@extension_router.post("/update", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def update(identifier: str, tag: str) -> Response:
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


@extension_router.post("/enable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def enable(identifier: str, tag: str) -> Response:
    ext = Extension(identifier, tag)
    return await ext.enable()


@extension_router.post("/disable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def disable(identifier: str, tag: str) -> Response:
    ext = Extension(identifier, tag)
    return await ext.disable()


@extension_router.post("/restart", status_code=status.HTTP_202_ACCEPTED)
@version(1, 0)
async def restart(identifier: str, tag: str) -> Response:
    ext = Extension(identifier, tag)
    return await ext.restart()
