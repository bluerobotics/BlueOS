from typing import Any, Dict, List, Set

from fastapi import APIRouter, Body, status
from fastapi_versioning import versioned_api_route

from autopilot_manager import AutoPilotManager
from mavlink_proxy.Endpoint import Endpoint

endpoints_router_v1 = APIRouter(
    prefix="/endpoints",
    tags=["extension_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = AutoPilotManager()


@endpoints_router_v1.get("/", response_model=List[Dict[str, Any]])
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@endpoints_router_v1.post("/", status_code=status.HTTP_201_CREATED)
async def create_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.add_new_endpoints(endpoints)


@endpoints_router_v1.delete("/", status_code=status.HTTP_200_OK)
async def remove_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.remove_endpoints(endpoints)


@endpoints_router_v1.put("/", status_code=status.HTTP_200_OK)
async def update_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.update_endpoints(endpoints)


@endpoints_router_v1.post("/unmanaged_board_master_endpoint", summary="Set the master endpoint for an unmanaged board.")
async def set_unmanaged_board_master_endpoint(endpoint: Endpoint) -> bool:
    return autopilot.set_unmanaged_board_master_endpoint(endpoint)


@endpoints_router_v1.get("/unmanaged_board_master_endpoint", summary="Get the master endpoint for an unmanaged board.")
def get_unmanaged_board_master_endpoint() -> Any:
    return autopilot.get_unmanaged_board_master_endpoint()
