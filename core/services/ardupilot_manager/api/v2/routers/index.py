from typing import Any, List, Optional

from api.v1.routers.index import index_to_http_exception
from autopilot_manager import AutoPilotManager
from fastapi import APIRouter, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import versioned_api_route
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
    """Return the running board.

    `platform.name` is the ArduPilot manifest platform name and `platform.platform_type` is serialized with
    capitalized values ("Serial", "Linux", "SITL", "Unknown", "Manual").
    """
    return autopilot.current_board


@index_router_v2.get(
    "/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards."
)
@index_to_http_exception
async def available_boards() -> Any:
    """List the connected boards, bootloaders included.

    `platform.name` is the ArduPilot manifest platform name and `platform.platform_type` is serialized with
    capitalized values ("Serial", "Linux", "SITL", "Unknown", "Manual").
    """
    return await autopilot.available_boards(True)
