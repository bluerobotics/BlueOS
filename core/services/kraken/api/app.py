# Path
from os import path
# FastAPI
from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI
from fastapi.staticfiles import StaticFiles
# Router
from api.routers import extension_router, kraken_router, container_router
# TEMP - REMOVE
from temp.apis import GenericErrorHandlingRoute

#
# Main API App
#

app = FastAPI(
    title="Kraken API",
    description="Kraken is the BlueOS service responsible for installing and managing extensions.",
)
app.router.route_class = GenericErrorHandlingRoute

# Adds the router to the app
app.include_router(kraken_router)
app.include_router(extension_router)
app.include_router(container_router)

# Adds API versioning
app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

# Mount static files
app.mount("/static", StaticFiles(directory=path.join(path.dirname(__file__), "static")), name="static")
