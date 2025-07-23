from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse
from fastapi_versioning import versioned_api_route

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@index_router_v1.get("/", status_code=200)
async def root() -> RedirectResponse:
    """
    Root endpoint for the Version Chooser API V1.
    """
    return RedirectResponse(url="/v1.0/docs")
