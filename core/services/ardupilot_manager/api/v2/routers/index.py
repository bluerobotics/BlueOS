from typing import Any, Optional
from fastapi import APIRouter, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import versioned_api_route
from autopilot_manager import AutoPilotManager
from api.v1.routers.index import index_to_http_exception
from typedefs import FlightController

index_router_v2 = APIRouter(
    tags=["index_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = AutoPilotManager()


@index_router_v2.get("/", status_code=status.HTTP_200_OK)
async def root_v2() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>AutoPilot Manager</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@index_router_v2.get(
    "/board", response_model=Optional[FlightController], summary="Check what is the current running board."
)
@index_to_http_exception
def get_board() -> Any:
    return autopilot.current_board
