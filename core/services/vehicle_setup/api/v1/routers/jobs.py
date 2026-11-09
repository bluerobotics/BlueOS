from typing import Any

from calibration.job import calibrate
from clients.mavlink import autopilot_link, is_armed
from config import SERVICE_NAME
from fastapi import APIRouter, HTTPException, status
from fastapi_versioning import versioned_api_route
from job_list.bus import HttpBus
from job_list.job import Cancel, JobRef, Refused
from job_list.kernel import Kernel, UnknownJob
from vehicle_setup_types import ConfirmPosition, StartCalibration

jobs_router_v1 = APIRouter(
    tags=["jobs_v1"],
    route_class=versioned_api_route(1, 0),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Unknown job"},
        status.HTTP_409_CONFLICT: {"description": "Refused"},
    },
)

bus = HttpBus(SERVICE_NAME)
kernel = Kernel(bus, {"Calibrate": calibrate(autopilot_link, is_armed)})


def signal(job: JobRef) -> JobRef:
    try:
        return kernel.signal(job)
    except UnknownJob as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@jobs_router_v1.post("/command/calibrate")
async def calibrate_command(request: StartCalibration) -> JobRef:
    try:
        return await kernel.submit("Calibrate", request)
    except Refused as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@jobs_router_v1.post("/command/confirm_position")
async def confirm_position(request: ConfirmPosition) -> JobRef:
    return signal(request)


@jobs_router_v1.post("/command/cancel")
async def cancel(request: Cancel) -> JobRef:
    return signal(request)


@jobs_router_v1.get("/state/{name:path}")
async def state(name: str) -> Any:
    try:
        return bus.value(name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no state {name}") from error
