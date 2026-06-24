from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse
from fastapi_versioning import versioned_api_route

index_router_v2 = APIRouter(
    tags=["index_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@index_router_v2.get("/", status_code=200)
async def root() -> RedirectResponse:
    """Root endpoint for the WiFi Manager API V2."""
    return RedirectResponse(url="/v2.0/docs")
