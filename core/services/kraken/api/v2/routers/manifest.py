from fastapi import APIRouter, status, HTTPException
from fastapi_versioning import version

from app.manifest import ManifestManager
from app.manifest.models import ManifestBase, Manifest

# Creates Extension router
manifest_router_v2 = APIRouter(
    prefix="/manifest",
    tags=["manifest"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

manager = ManifestManager.instance()

# Endpoints

@manifest_router_v2.get("/", status_code=status.HTTP_200_OK)
@version(2, 0)
async def list_manifest() -> list[Manifest]:
    return await manager.fetch()

@manifest_router_v2.get("/{identifier}", status_code=status.HTTP_200_OK)
@version(2, 0)
async def get_manifest(identifier: str) -> Manifest:
    manifest = await manager.fetch_by_identifier(identifier)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manifest not found")

    return manifest

@manifest_router_v2.post("/", status_code=status.HTTP_201_CREATED)
@version(2, 0)
async def create_manifest(body: ManifestBase) -> str:
    return await manager.add(body)

@manifest_router_v2.put("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
@version(2, 0)
async def update_manifest(identifier: str, body: ManifestBase) -> None:
    await manager.update(identifier, body)

@manifest_router_v2.delete("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
@version(2, 0)
async def delete_manifest(identifier: str) -> None:
    await manager.remove(identifier)
