from typing import Any, List

from commonwealth.service.service import Service
from fastapi import APIRouter, status
from fastapi_versioning import version
from loguru import logger
from nmea_injector.schemas import SockRequest
from nmea_injector.TrafficController import NMEASocket, TrafficController
from nmea_injector.views import SockSummary


def build_nmea_router(service: Service[TrafficController], controller: TrafficController) -> APIRouter:
    router = APIRouter()

    @router.get("/socks", response_model=List[SockSummary])
    @version(1, 0)
    def list_socks() -> Any:
        with service.read() as view:
            socks = list(view.socks)
        logger.debug(f"Available NMEA sockets: {[str(sock) for sock in socks]}.")
        return socks

    @router.post("/socks", status_code=status.HTTP_201_CREATED)
    @version(1, 0)
    async def add_sock(body: SockRequest) -> Any:
        cmd = body.to_add()
        logger.debug(f"Adding sock '{cmd}'.")
        server = await controller.listen(NMEASocket.from_command(cmd))
        with service.write() as state:
            state.apply_add(cmd, server)
        logger.debug(f"Sock '{cmd}' added.")

    @router.delete("/socks", status_code=status.HTTP_200_OK)
    @version(1, 0)
    def remove_sock(body: SockRequest) -> Any:
        cmd = body.to_remove()
        logger.debug(f"Removing sock '{cmd}'.")
        with service.write() as state:
            state.apply_remove(cmd)
        logger.debug(f"Sock '{cmd}' removed.")

    return router
