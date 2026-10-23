import base64

from eeprom.manager import EEPROMManager
from fastapi import APIRouter, HTTPException, status
from fastapi_versioning import versioned_api_route

eeprom_router_v1 = APIRouter(
    prefix="/eeprom",
    tags=["eeprom_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

manager = EEPROMManager()


@eeprom_router_v1.get("/status", status_code=status.HTTP_200_OK)
async def get_status() -> dict[str, str | bool]:
    return {"status": manager.status().name, "mavlink": await manager.mavlink_online()}


@eeprom_router_v1.post("/backup", status_code=status.HTTP_200_OK)
async def backup() -> dict[str, float]:
    try:
        return await manager.backup()
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@eeprom_router_v1.get("/backup", status_code=status.HTTP_200_OK)
async def get_backup() -> dict[str, float]:
    calibration = manager.read_calibration()
    if calibration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid backup found on the EEPROM.")
    return calibration.to_params()


@eeprom_router_v1.get("/dump", status_code=status.HTTP_200_OK)
async def dump() -> dict[str, str | int | None]:
    calibration = manager.read_calibration()
    return {
        "data": base64.b64encode(manager.dump()).decode("utf-8"),
        "backup_offset": calibration.offset if calibration else None,
        "hat_size": manager.eeprom.hat_id_partition_size(),
    }
