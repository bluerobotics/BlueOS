from os import path

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.zenoh_helper import ZenohRouter, zenoh_session
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI

# Routers
from api.v1.routers import extension_router_v1, index_router_v1
from api.v2.routers import (
    container_router_v2,
    extension_router_v2,
    index_router_v2,
    jobs_router_v2,
    manifest_router_v2,
    zenoh_container_router,
    zenoh_extension_router,
    zenoh_jobs_router,
    zenoh_manifest_router,
)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:  # pylint: disable=unused-argument
    yield
    zenoh_session.close()


application = FastAPI(
    title="Kraken API",
    description="Kraken is the BlueOS service responsible for installing and managing extensions.",
)
application.router.route_class = GenericErrorHandlingRoute

# API v1
application.include_router(index_router_v1)
application.include_router(extension_router_v1)

# API v2
application.include_router(index_router_v2)
application.include_router(container_router_v2)
application.include_router(extension_router_v2)
application.include_router(jobs_router_v2)
application.include_router(manifest_router_v2)

application = VersionedFastAPI(application, prefix_format="/v{major}.{minor}", enable_latest=True, lifespan=lifespan)

# Zenoh
zenoh_router = ZenohRouter("kraken")
zenoh_router.include_router(zenoh_container_router)
zenoh_router.include_router(zenoh_extension_router)
zenoh_router.include_router(zenoh_jobs_router)
zenoh_router.include_router(zenoh_manifest_router)

zenoh_router.declare()


@application.get("/", status_code=200)
async def root() -> RedirectResponse:
    """
    Root endpoint for the Kraken.
    """

    return RedirectResponse(url="/static/pages/root.html")


# Mount static files
application.mount("/static", StaticFiles(directory=path.join(path.dirname(__file__), "static")), name="static")
