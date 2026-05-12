#! /usr/bin/env python3

import asyncio
import json
import logging
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile, status
from fastapi_versioning import VersionedFastAPI, versioned_api_route
from loguru import logger
from pydantic import BaseModel, Field
from storage import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_MODEL_EXTENSIONS,
    BRANDING_DIR,
    LOGO_BASENAME,
    MODELS_DIR,
    THEME_CONFIG_FILE,
    THEME_FILE,
    VEHICLE_IMAGE_BASENAME,
    ensure_dirs,
    find_branding_file,
    remove_branding_file,
    safe_join,
)
from theme import derive_palette, parse_hex, render_css
from uvicorn import Config, Server

SERVICE_NAME = "customization"
PORT = 9152
DEFAULT_PRIMARY = "#2699D0"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
init_logger(SERVICE_NAME)
logger.info("Starting Customization service")


class ThemeConfig(BaseModel):
    primary: str = Field(..., description="Primary color in #RRGGBB format")


class ThemeStatus(BaseModel):
    primary: str = Field(..., description="Current primary color")
    palette: Dict[str, str] = Field(..., description="Derived palette anchors")
    css_url: str = Field(..., description="URL where the generated CSS is served")


class ModelEntry(BaseModel):
    name: str = Field(..., description="Relative path under modeloverrides/")
    size_bytes: int = Field(..., description="File size in bytes")
    url: str = Field(..., description="URL where the model is served")


class BrandingAsset(BaseModel):
    url: Optional[str] = Field(None, description="URL where the asset is served, if present")
    size_bytes: Optional[int] = Field(None, description="File size in bytes, if present")


def to_http_exception(endpoint: Any) -> Any:
    is_async = asyncio.iscoroutinefunction(endpoint)

    @wraps(endpoint)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            if is_async:
                return await endpoint(*args, **kwargs)
            return endpoint(*args, **kwargs)
        except HTTPException as exception:
            raise exception
        except ValueError as exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exception)) from exception
        except Exception as exception:
            logger.exception("Customization endpoint failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exception)) from exception

    return wrapper


def load_theme_config() -> ThemeConfig:
    if THEME_CONFIG_FILE.exists():
        try:
            data = json.loads(THEME_CONFIG_FILE.read_text(encoding="utf-8"))
            return ThemeConfig(**data)
        except Exception as exception:
            logger.warning(f"Failed to read theme config, falling back to default: {exception}")
    return ThemeConfig(primary=DEFAULT_PRIMARY)


def save_theme_config(config: ThemeConfig) -> None:
    ensure_dirs()
    THEME_CONFIG_FILE.write_text(json.dumps(config.dict(), indent=2), encoding="utf-8")


def write_theme_css(primary: str) -> None:
    ensure_dirs()
    THEME_FILE.write_text(render_css(primary), encoding="utf-8")


async def save_upload(upload: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    chunk_size = 1024 * 1024
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds {limit_mb} MB.",
                )
            out.write(chunk)
    return written


theme_router = APIRouter(
    prefix="/theme",
    tags=["theme"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@theme_router.get("", response_model=ThemeStatus, summary="Get the current theme configuration.")
@to_http_exception
async def get_theme() -> ThemeStatus:
    config = load_theme_config()
    palette = derive_palette(config.primary)
    if not THEME_FILE.exists():
        write_theme_css(config.primary)
    return ThemeStatus(primary=config.primary, palette=palette, css_url="/userdata/styles/theme_style.css")


@theme_router.put("", response_model=ThemeStatus, summary="Set the primary color and regenerate the theme CSS.")
@to_http_exception
async def set_theme(config: ThemeConfig) -> ThemeStatus:
    ensure_dirs()
    # Validate via parse_hex so to_http_exception turns invalid input into a 400.
    parse_hex(config.primary)
    save_theme_config(config)
    write_theme_css(config.primary)
    palette = derive_palette(config.primary)
    return ThemeStatus(primary=config.primary, palette=palette, css_url="/userdata/styles/theme_style.css")


@theme_router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Reset the theme to defaults.")
@to_http_exception
async def reset_theme() -> None:
    THEME_CONFIG_FILE.unlink(missing_ok=True)
    THEME_FILE.unlink(missing_ok=True)
    write_theme_css(DEFAULT_PRIMARY)


models_router = APIRouter(
    prefix="/models",
    tags=["models"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def list_model_files() -> List[ModelEntry]:
    if not MODELS_DIR.exists():
        return []
    entries: List[ModelEntry] = []
    for path in sorted(MODELS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_MODEL_EXTENSIONS:
            continue
        rel = path.relative_to(MODELS_DIR).as_posix()
        entries.append(
            ModelEntry(
                name=rel,
                size_bytes=path.stat().st_size,
                url=f"/userdata/modeloverrides/{rel}",
            )
        )
    return entries


@models_router.get("", response_model=List[ModelEntry], summary="List uploaded model overrides.")
@to_http_exception
async def list_models() -> List[ModelEntry]:
    ensure_dirs()
    return list_model_files()


@models_router.post("", response_model=ModelEntry, summary="Upload a model override (.glb).")
@to_http_exception
async def upload_model(
    name: str,
    file: UploadFile = File(...),
) -> ModelEntry:
    ensure_dirs()
    target = safe_join(MODELS_DIR, name)
    if target.suffix.lower() not in ALLOWED_MODEL_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {sorted(ALLOWED_MODEL_EXTENSIONS)} files are allowed.",
        )
    written = await save_upload(file, target)
    rel = target.relative_to(MODELS_DIR).as_posix()
    return ModelEntry(name=rel, size_bytes=written, url=f"/userdata/modeloverrides/{rel}")


@models_router.delete(
    "/{name:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a model override.",
)
@to_http_exception
async def delete_model(name: str) -> None:
    target = safe_join(MODELS_DIR, name)
    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found.")
    target.unlink()


branding_router = APIRouter(
    prefix="/branding",
    tags=["branding"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def branding_asset(basename: str) -> BrandingAsset:
    existing = find_branding_file(basename)
    if existing is None:
        return BrandingAsset()
    return BrandingAsset(
        url=f"/userdata/branding/{existing.name}",
        size_bytes=existing.stat().st_size,
    )


def validate_image_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {sorted(ALLOWED_IMAGE_EXTENSIONS)} files are allowed.",
        )
    return suffix


async def replace_branding_asset(basename: str, file: UploadFile) -> BrandingAsset:
    ensure_dirs()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename.")
    suffix = validate_image_extension(file.filename)
    remove_branding_file(basename)
    target = safe_join(BRANDING_DIR, f"{basename}{suffix}")
    written = await save_upload(file, target)
    return BrandingAsset(url=f"/userdata/branding/{target.name}", size_bytes=written)


@branding_router.get("/logo", response_model=BrandingAsset, summary="Get the current custom logo, if any.")
@to_http_exception
async def get_logo() -> BrandingAsset:
    return branding_asset(LOGO_BASENAME)


@branding_router.post("/logo", response_model=BrandingAsset, summary="Upload a custom company logo.")
@to_http_exception
async def upload_logo(file: UploadFile = File(...)) -> BrandingAsset:
    return await replace_branding_asset(LOGO_BASENAME, file)


@branding_router.delete("/logo", status_code=status.HTTP_204_NO_CONTENT, summary="Remove the custom logo.")
@to_http_exception
async def delete_logo() -> None:
    remove_branding_file(LOGO_BASENAME)


@branding_router.get(
    "/vehicle-image",
    response_model=BrandingAsset,
    summary="Get the current custom vehicle image, if any.",
)
@to_http_exception
async def get_vehicle_image() -> BrandingAsset:
    return branding_asset(VEHICLE_IMAGE_BASENAME)


@branding_router.post(
    "/vehicle-image",
    response_model=BrandingAsset,
    summary="Upload a custom vehicle image.",
)
@to_http_exception
async def upload_vehicle_image(file: UploadFile = File(...)) -> BrandingAsset:
    return await replace_branding_asset(VEHICLE_IMAGE_BASENAME, file)


@branding_router.delete(
    "/vehicle-image",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove the custom vehicle image.",
)
@to_http_exception
async def delete_vehicle_image() -> None:
    remove_branding_file(VEHICLE_IMAGE_BASENAME)


fast_api_app = FastAPI(
    title="Customization API",
    description="Manage BlueOS visual customization (theme color, 3D model overrides, branding).",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute
fast_api_app.include_router(theme_router)
fast_api_app.include_router(models_router)
fast_api_app.include_router(branding_router)

app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"service": SERVICE_NAME}


async def main() -> None:
    try:
        await init_sentry_async(SERVICE_NAME)
        ensure_dirs()
        # Make sure the CSS exists on first boot so index.html's <link> doesn't 404
        if not THEME_FILE.exists():
            write_theme_css(load_theme_config().primary)

        config = Config(app=app, host="0.0.0.0", port=PORT, log_config=None)
        server = Server(config)
        await server.serve()
    finally:
        logger.info("Customization service stopped")


if __name__ == "__main__":
    asyncio.run(main())
