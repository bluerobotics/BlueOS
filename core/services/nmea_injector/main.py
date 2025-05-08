#! /usr/bin/env python3
import argparse
import asyncio
import logging
from typing import Any, List

from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import FastAPI, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

from nmea_injector.TrafficController import NMEASocket, SocketKind, TrafficController

SERVICE_NAME = "nmea-injector"

parser = argparse.ArgumentParser(description="NMEA Injector service for Blue Robotics BlueOS")
parser.add_argument("-u", "--udp", type=int, help="change the default UDP input port")
parser.add_argument("-t", "--tcp", type=int, help="change the default TCP input port")

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)


app = FastAPI(
    title="NMEA Injector API",
    description="NMEA Injector is a service responsible for injecting external NMEA data on the Mavlink stream.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Starting NMEA Injector.")
controller = TrafficController()


@app.get("/socks", response_model=List[NMEASocket])
@version(1, 0)
def get_socks() -> Any:
    socks = controller.get_socks()
    logger.debug(f"Available NMEA sockets: {[str(sock) for sock in socks]}.")
    return socks


@app.post(
    "/socks",
    status_code=status.HTTP_201_CREATED,
    summary="Add new NMEA socket.",
    description="Component ID refers to the Mavlink specification. Usual for GPS units are 220 and 221.",
)
@version(1, 0)
async def add_sock(sock: NMEASocket) -> Any:
    await controller.add_sock(sock)


@app.delete(
    "/socks",
    status_code=status.HTTP_200_OK,
    summary="Remove existing NMEA socket.",
)
@version(1, 0)
def remove_sock(sock: NMEASocket) -> Any:
    controller.remove_sock(sock)


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def read_items() -> Any:
    html_content = """
    <html>
        <head>
            <title>NMEA Injector</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=2748, log_config=None)
    server = Server(config)

    loop.create_task(controller.load_socks_from_settings())
    if args.udp:
        loop.create_task(controller.add_sock(NMEASocket(kind=SocketKind.UDP, port=args.udp, component_id=220)))
    if args.tcp:
        loop.create_task(controller.add_sock(NMEASocket(kind=SocketKind.TCP, port=args.tcp, component_id=221)))
    loop.run_until_complete(server.serve())
