from typing import Any, Dict, List, Set

from fastapi import APIRouter, Body, status
from fastapi_versioning import versioned_api_route

from ArduPilotManager import ArduPilotManager
from mavlink_proxy.Endpoint import Endpoint

endpoints_router_v1 = APIRouter(
    prefix="/endpoints",
    tags=["extension_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = ArduPilotManager()


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
