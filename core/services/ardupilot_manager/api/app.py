from os import path

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI

# Routers
from api.v1.routers import endpoints_router_v1, index_router_v1
from api.v2.routers import index_router_v2

application = FastAPI(
    title="ArduPilot Manager API",
    description="ArduPilot Manager is responsible for managing ArduPilot devices connected to BlueOS.",
    default_response_class=PrettyJSONResponse,
    debug=True,  # TODO - Add debug after based on args
)
application.router.route_class = GenericErrorHandlingRoute

# API v1
application.include_router(index_router_v1)
application.include_router(endpoints_router_v1)

# API v2
application.include_router(index_router_v2)

application = VersionedFastAPI(application, prefix_format="/v{major}.{minor}", enable_latest=True)


@application.get("/", status_code=200)
async def root() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>ArduPilot Manager</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


# Mount static files
application.mount("/static", StaticFiles(directory=path.join(path.dirname(__file__), "static")), name="static")
