# Path
from os import path
# FastAPI
from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI
from fastapi.staticfiles import StaticFiles
# Routers
from api.v1.routers import index_router_v1, extension_router_v1
from api.v2.routers import index_router_v2, extension_router_v2, container_router_v2
from commonwealth.utils.apis import GenericErrorHandlingRoute

#
# Main API App
#

app = FastAPI(
    title="Kraken API",
    description="Kraken is the BlueOS service responsible for installing and managing extensions.",
)
app.router.route_class = GenericErrorHandlingRoute

# Adds routers to the app

# API v1
app.include_router(index_router_v1)
app.include_router(extension_router_v1)

# API v2
app.include_router(index_router_v2)
app.include_router(extension_router_v2)
app.include_router(container_router_v2)

# Adds API versioning
app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

# Mount static files
app.mount("/static", StaticFiles(directory=path.join(path.dirname(__file__), "static")), name="static")
