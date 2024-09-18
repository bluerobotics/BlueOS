import os
import shutil
from pathlib import Path
from typing import Any, List, Optional

from commonwealth.mavlink_comm.exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)
from commonwealth.mavlink_comm.typedefs import FirmwareInfo, MavlinkVehicleType
from commonwealth.utils.apis import StackedHTTPException
from commonwealth.utils.decorators import single_threaded
from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from fastapi_versioning import versioned_api_route
from loguru import logger

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
from typedefs import Firmware, FlightController, Parameters, Serial, SITLFrame, Vehicle

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = ArduPilotManager()


# By default, all REST resources should have its own router, but as some of them does not implement
# all the CRUD operations, we gonna keep ones that have less than 2 endpoints in the index router.


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


@index_router_v1.put("/serials", status_code=status.HTTP_200_OK)
def update_serials(serials: List[Serial] = Body(...)) -> Any:
    autopilot.update_serials(serials)


@index_router_v1.get("/serials", response_model=List[Serial])
def get_serials() -> Any:
    return autopilot.get_serials()


@index_router_v1.get("/firmware_info", response_model=FirmwareInfo, summary="Get version and type of current firmware.")
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


@index_router_v1.get("/vehicle_type", response_model=MavlinkVehicleType, summary="Get mavlink vehicle type.")
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


@index_router_v1.post("/sitl_frame", summary="Set SITL Frame type.")
async def set_sitl_frame(frame: SITLFrame) -> Any:
    return autopilot.set_sitl_frame(frame)


@index_router_v1.get("/firmware_vehicle_type", response_model=str, summary="Get firmware vehicle type.")
async def get_firmware_vehicle_type() -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch vehicle type info as there's no board running.")
    return await autopilot.vehicle_manager.get_firmware_vehicle_type()


@index_router_v1.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
async def get_available_firmwares(vehicle: Vehicle, board_name: Optional[str] = None) -> Any:
    return autopilot.get_available_firmwares(vehicle, (await target_board(board_name)).platform)


@index_router_v1.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@single_threaded(callback=raise_lock)
async def install_firmware_from_url(
    url: str,
    board_name: Optional[str] = None,
    make_default: bool = False,
    parameters: Optional[Parameters] = None,
    auto_switch_board: bool = True,
) -> Any:
    board = None
    try:
        await autopilot.kill_ardupilot()
        board = await target_board(board_name)
        autopilot.install_firmware_from_url(url, board, make_default, parameters)
    finally:
        await autopilot.start_ardupilot()

    # In some cases user might install a firmware that implies in a board change but this is not reflected,
    # so if the board is different from the current one, we change it.
    if auto_switch_board and board and autopilot.current_board and autopilot.current_board.name != board.name:
        await autopilot.change_board(board)


@index_router_v1.post("/install_firmware_from_file", summary="Install firmware from user file.")
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


@index_router_v1.get("/board", response_model=FlightController, summary="Check what is the current running board.")
def get_board() -> Any:
    return autopilot.current_board


@index_router_v1.post("/board", summary="Set board to be used.")
async def set_board(board: FlightController, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> Any:
    autopilot.current_sitl_frame = sitl_frame
    await autopilot.change_board(board)


@index_router_v1.post("/restart", summary="Restart the autopilot with current set options.")
async def restart() -> Any:
    logger.debug("Restarting ardupilot...")
    await autopilot.restart_ardupilot()
    logger.debug("Ardupilot successfully restarted.")


@index_router_v1.post("/start", summary="Start the autopilot.")
async def start() -> Any:
    logger.debug("Starting ardupilot...")
    await autopilot.start_ardupilot()
    logger.debug("Ardupilot successfully started.")


@index_router_v1.post("/preferred_router", summary="Set the preferred MAVLink router.")
async def set_preferred_router(router: str) -> Any:
    logger.debug("Setting preferred Router")
    await autopilot.set_preferred_router(router)
    logger.debug(f"Preferred Router successfully set to {router}")


@index_router_v1.get("/preferred_router", summary="Retrieve preferred router")
def preferred_router() -> Any:
    return autopilot.load_preferred_router()


@index_router_v1.get("/available_routers", summary="Retrieve preferred router")
def available_routers() -> Any:
    return autopilot.get_available_routers()


@index_router_v1.post("/stop", summary="Stop the autopilot.")
async def stop() -> Any:
    logger.debug("Stopping ardupilot...")
    await autopilot.kill_ardupilot()
    logger.debug("Ardupilot successfully stopped.")


@index_router_v1.post("/restore_default_firmware", summary="Restore default firmware.")
async def restore_default_firmware(board_name: Optional[str] = None) -> Any:
    try:
        await autopilot.kill_ardupilot()
        autopilot.restore_default_firmware(await target_board(board_name))
    finally:
        await autopilot.start_ardupilot()


@index_router_v1.get(
    "/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards."
)
async def available_boards() -> Any:
    return await autopilot.available_boards(True)
