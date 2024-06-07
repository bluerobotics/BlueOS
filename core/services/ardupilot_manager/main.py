#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from commonwealth.mavlink_comm.exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)
from commonwealth.mavlink_comm.typedefs import FirmwareInfo, MavlinkVehicleType
from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    StackedHTTPException,
)
from commonwealth.utils.decorators import single_threaded
from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import Body, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
from flight_controller_detector.Detector import Detector as BoardDetector
from mavlink_proxy.Endpoint import Endpoint
from settings import SERVICE_NAME
from typedefs import Firmware, FlightController, Parameters, Serial, SITLFrame, Vehicle

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")

parser = argparse.ArgumentParser(description="ArduPilot Manager service for Blue Robotics BlueOS")
parser.add_argument("-s", "--sitl", help="run SITL instead of connecting any board", action="store_true")

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

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


async def target_board(board_name: Optional[str]) -> FlightController:
    """Returns the board that should be used to perform operations on.

    Most of the API routes that have operations related to board management will give the option to perform those
    operations on the running board or on some of the connected boards. This function abstract this logic that is
    common on all the routes.

    If the `board_name` argument is None, it will check if there's a running board, and return it if so. If one
    provides the `board_name`, this function will check if there's a connected board with that name and return it if so.
    """
    if board_name is not None:
        try:
            return next(board for board in await autopilot.available_boards(True) if board.name == board_name)
        except StopIteration as error:
            raise ValueError("Chosen board not available.") from error
    if autopilot.current_board is None:
        raise RuntimeError("No board running and no target board set.")
    return autopilot.current_board


def raise_lock(*raise_args: str, **kwargs: int) -> None:
    """Raise a 423 HTTP Error status

    Raises:
        HTTPException: Exception that the operation is already in progress.
    """
    raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Operation already in progress.")


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def create_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.add_new_endpoints(endpoints)


@app.delete("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
async def remove_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.remove_endpoints(endpoints)


@app.put("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
async def update_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    await autopilot.update_endpoints(endpoints)


@app.put("/serials", status_code=status.HTTP_200_OK)
@version(1, 0)
def update_serials(serials: List[Serial] = Body(...)) -> Any:
    autopilot.update_serials(serials)


@app.get("/serials", response_model=List[Serial])
@version(1, 0)
def get_serials() -> Any:
    return autopilot.get_serials()


@app.get("/firmware_info", response_model=FirmwareInfo, summary="Get version and type of current firmware.")
@version(1, 0)
async def get_firmware_info() -> Any:
    if not autopilot.current_board:
        message = "No board running, firmware information is unavailable"
        logger.warning(message)
        return PlainTextResponse(message, status_code=503)
    try:
        return await autopilot.vehicle_manager.get_firmware_info()
    except ValueError:
        return PlainTextResponse("Failed to get autopilot version", status_code=500)
    except MavlinkMessageSendFail:
        return PlainTextResponse("Timed out requesting Firmware Info message", status_code=500)


@app.get("/vehicle_type", response_model=MavlinkVehicleType, summary="Get mavlink vehicle type.")
@version(1, 0)
async def get_vehicle_type() -> Any:
    if not autopilot.current_board:
        message = "No board running, vehicle type is unavailable"
        logger.warning(message)
        return PlainTextResponse(message, status_code=503)
    try:
        return await autopilot.vehicle_manager.get_vehicle_type()
    except FetchUpdatedMessageFail as error:
        return PlainTextResponse(f"Timed out fetching message: {error}", status_code=500)
    except MavlinkMessageReceiveFail as error:
        return PlainTextResponse(f"Failed to get vehicle type: {error}", status_code=500)


@app.post("/sitl_frame", summary="Set SITL Frame type.")
@version(1, 0)
async def set_sitl_frame(frame: SITLFrame) -> Any:
    return autopilot.set_sitl_frame(frame)


@app.get("/firmware_vehicle_type", response_model=str, summary="Get firmware vehicle type.")
@version(1, 0)
async def get_firmware_vehicle_type() -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch vehicle type info as there's no board running.")
    return await autopilot.vehicle_manager.get_firmware_vehicle_type()


@app.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@version(1, 0)
async def get_available_firmwares(vehicle: Vehicle, board_name: Optional[str] = None) -> Any:
    return autopilot.get_available_firmwares(vehicle, (await target_board(board_name)).platform)


@app.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@version(1, 0)
@single_threaded(callback=raise_lock)
async def install_firmware_from_url(
    url: str,
    board_name: Optional[str] = None,
    make_default: bool = False,
    parameters: Optional[Parameters] = None,
) -> Any:
    try:
        await autopilot.kill_ardupilot()
        autopilot.install_firmware_from_url(url, await target_board(board_name), make_default, parameters)
    finally:
        await autopilot.start_ardupilot()


@app.post("/install_firmware_from_file", summary="Install firmware from user file.")
@version(1, 0)
@single_threaded(callback=raise_lock)
async def install_firmware_from_file(
    binary: UploadFile = File(...),
    board_name: Optional[str] = None,
    parameters: Optional[Parameters] = None,
) -> Any:
    try:
        custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
        logger.debug("Going to kill ardupilot")
        await autopilot.kill_ardupilot()
        logger.debug("Installing firmware from file")
        autopilot.install_firmware_from_file(custom_firmware, await target_board(board_name), parameters)
        os.remove(custom_firmware)
    except InvalidFirmwareFile as error:
        raise StackedHTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, error=error) from error
    finally:
        binary.file.close()
        logger.debug("Starting ardupilot again")
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


@app.post("/preferred_router", summary="Set the preferred MAVLink router.")
@version(1, 0)
async def set_preferred_router(router: str) -> Any:
    logger.debug("Setting preferred Router")
    await autopilot.set_preferred_router(router)
    logger.debug(f"Preferred Router successfully set to {router}")


@app.get("/preferred_router", summary="Retrieve preferred router")
@version(1, 0)
def preferred_router() -> Any:
    return autopilot.load_preferred_router()


@app.get("/available_routers", summary="Retrieve preferred router")
@version(1, 0)
def available_routers() -> Any:
    return autopilot.get_available_routers()


@app.post("/stop", summary="Stop the autopilot.")
@version(1, 0)
async def stop() -> Any:
    logger.debug("Stopping ardupilot...")
    await autopilot.kill_ardupilot()
    logger.debug("Ardupilot successfully stopped.")


@app.post("/restore_default_firmware", summary="Restore default firmware.")
@version(1, 0)
async def restore_default_firmware(board_name: Optional[str] = None) -> Any:
    try:
        await autopilot.kill_ardupilot()
        autopilot.restore_default_firmware(await target_board(board_name))
    finally:
        await autopilot.start_ardupilot()


@app.get("/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards.")
@version(1, 0)
async def available_boards() -> Any:
    return await autopilot.available_boards(True)


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def root() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>ArduPilot Manager</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


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
