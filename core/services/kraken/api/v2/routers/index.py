from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse, StreamingResponse, PlainTextResponse
from fastapi_versioning import version

from kraken import Kraken

# Creates Root Kraken router
index_router_v2 = APIRouter(
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not found"}
    },
)

# Endpoints

@index_router_v2.get("/", response_class=RedirectResponse, status_code=200)
@version(2, 0)
async def root() -> RedirectResponse:
    """
    Root endpoint for the Kraken API V2.
    """

    return RedirectResponse(url="/static/pages/root.html")


@index_router_v2.get("/log", response_class=PlainTextResponse, status_code=200)
@version(2, 0)
async def log(container_name: str) -> StreamingResponse:
    """
    Get logs from current running Kraken instance.
    """

    return StreamingResponse(Kraken.log(container_name), media_type="text/plain")
