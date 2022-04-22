#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Set

from commonwealth.mavlink_comm.typedefs import FirmwareInfo, MavlinkVehicleType
from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    StackedHTTPException,
)
from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler, get_new_log_path
from fastapi import Body, FastAPI, File, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
from flight_controller_detector.Detector import Detector as BoardDetector
from mavlink_proxy.Endpoint import Endpoint
from settings import SERVICE_NAME
from typedefs import Firmware, FlightController, SITLFrame, Vehicle

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")

parser = argparse.ArgumentParser(description="ArduPilot Manager service for Blue Robotics BlueOS")
parser.add_argument("-s", "--sitl", help="run SITL instead of connecting any board", action="store_true")

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
logger.add(get_new_log_path(SERVICE_NAME))


app = FastAPI(
    title="ArduPilot Manager API",
    description="ArduPilot Manager is responsible for managing ArduPilot devices connected to BlueOS.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Starting ArduPilot Manager.")
autopilot = ArduPilotManager()
if not is_running_as_root():
    raise RuntimeError("ArduPilot manager needs to run with root privilege.")


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
def create_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    autopilot.add_new_endpoints(endpoints)


@app.delete("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def remove_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    autopilot.remove_endpoints(endpoints)


@app.put("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def update_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    autopilot.update_endpoints(endpoints)


@app.get("/firmware_info", response_model=FirmwareInfo, summary="Get version and type of current firmware.")
@version(1, 0)
async def get_firmware_info() -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch firmware info as there's no board running.")
    return await autopilot.vehicle_manager.get_firmware_info()


@app.get("/vehicle_type", response_model=MavlinkVehicleType, summary="Get mavlink vehicle type.")
@version(1, 0)
async def get_vehicle_type() -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch vehicle type info as there's no board running.")
    return await autopilot.vehicle_manager.get_vehicle_type()


@app.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@version(1, 0)
def get_available_firmwares(vehicle: Vehicle) -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch available firmwares as there's no board running.")
    return autopilot.get_available_firmwares(vehicle, autopilot.current_board.platform)


@app.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@version(1, 0)
async def install_firmware_from_url(url: str) -> Any:
    try:
        if not autopilot.current_board:
            raise RuntimeError("Cannot install firmware as there's no board running.")
        await autopilot.kill_ardupilot()
        autopilot.install_firmware_from_url(url, autopilot.current_board)
    finally:
        await autopilot.start_ardupilot()


@app.post("/install_firmware_from_file", summary="Install firmware from user file.")
@version(1, 0)
async def install_firmware_from_file(binary: UploadFile = File(...)) -> Any:
    custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
    try:
        if not autopilot.current_board:
            raise RuntimeError("Cannot install firmware as there's no board running.")
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
        await autopilot.kill_ardupilot()
        autopilot.install_firmware_from_file(custom_firmware, autopilot.current_board)
        os.remove(custom_firmware)
    except InvalidFirmwareFile as error:
        raise StackedHTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, error=error) from error
    finally:
        binary.file.close()
        await autopilot.start_ardupilot()


@app.get("/board", response_model=FlightController, summary="Check what is the current running board.")
@version(1, 0)
def get_board() -> Any:
    return autopilot.current_board


@app.post("/board", summary="Set board to be used.")
@version(1, 0)
async def set_board(board: FlightController, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> Any:
    autopilot.current_sitl_frame = sitl_frame
    await autopilot.change_board(board)


@app.post("/restart", summary="Restart the autopilot with current set options.")
@version(1, 0)
async def restart() -> Any:
    logger.debug("Restarting ardupilot...")
    await autopilot.restart_ardupilot()
    logger.debug("Ardupilot successfully restarted.")


@app.post("/start", summary="Start the autopilot.")
@version(1, 0)
async def start() -> Any:
    logger.debug("Starting ardupilot...")
    await autopilot.start_ardupilot()
    logger.debug("Ardupilot successfully started.")


@app.post("/stop", summary="Stop the autopilot.")
@version(1, 0)
async def stop() -> Any:
    logger.debug("Stopping ardupilot...")
    await autopilot.kill_ardupilot()
    logger.debug("Ardupilot successfully stopped.")


@app.post("/restore_default_firmware", summary="Restore default firmware.")
@version(1, 0)
async def restore_default_firmware() -> Any:
    try:
        if not autopilot.current_board:
            raise RuntimeError("Cannot restore firmware as there's no board running.")
        await autopilot.kill_ardupilot()
        autopilot.restore_default_firmware(autopilot.current_board)
    finally:
        await autopilot.start_ardupilot()


@app.get("/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards.")
@version(1, 0)
def available_boards() -> Any:
    return BoardDetector.detect()


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=8000, log_config=None)
    server = Server(config)

    if args.sitl:
        autopilot.set_preferred_board(BoardDetector.detect_sitl())
    try:
        loop.run_until_complete(autopilot.start_ardupilot())
    except Exception as start_error:
        logger.exception(start_error)
    loop.create_task(autopilot.auto_restart_ardupilot())
    loop.create_task(autopilot.start_mavlink_manager_watchdog())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(autopilot.kill_ardupilot())
