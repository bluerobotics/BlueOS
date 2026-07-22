from typing import Any, List

from commonwealth.service.service import Service
from fastapi import APIRouter, status
from fastapi_versioning import version
from loguru import logger
from ports import SerialCatalog
from schemas import BridgeRequest
from service import BridgetState
from views import BridgeSummary


def build_bridget_router(service: Service[BridgetState], catalog: SerialCatalog) -> APIRouter:
    router = APIRouter()

    @router.get("/serial_ports", response_model=List[str])
    @version(1, 0)
    def list_serial_ports() -> Any:
        ports = catalog.list_ports()
        logger.debug(f"Available serial ports found: {ports}.")
        return ports

    @router.get("/bridges", response_model=List[BridgeSummary])
    @version(1, 0)
    def list_bridges() -> Any:
        with service.read() as view:
            bridges = list(view.bridges)
        logger.debug(bridges)
        return bridges

    @router.post("/bridges", status_code=status.HTTP_201_CREATED)
    @version(1, 0)
    def add_bridge(body: BridgeRequest) -> Any:
        cmd = body.to_add()
        logger.debug(f"Adding bridge '{cmd}'.")
        with service.write() as state:
            state.apply_add(cmd)
        logger.debug(f"Bridge '{cmd}' added.")

    @router.delete("/bridges", status_code=status.HTTP_200_OK)
    @version(1, 0)
    def remove_bridge(body: BridgeRequest) -> Any:
        cmd = body.to_remove()
        logger.debug(f"Removing bridge '{cmd}'.")
        with service.write() as state:
            state.apply_remove(cmd)
        logger.debug(f"Bridge '{cmd}' removed.")

    return router
