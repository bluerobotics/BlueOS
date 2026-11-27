import asyncio
import json
import shutil
from contextlib import contextmanager
from functools import partial, wraps
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Iterator,
    List,
    NoReturn,
    Optional,
    Tuple,
)

from autopilot_manager import (
    AutoPilotManager,
    board_matches_preferred,
    is_same_hardware,
)
from commonwealth.mavlink_comm.exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)
from commonwealth.mavlink_comm.typedefs import FirmwareInfo, MavlinkVehicleType
from exceptions import InvalidFirmwareFile, NoDefaultFirmwareAvailable
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi_versioning import versioned_api_route
from firmware.install_job import (
    FirmwareInstallJob,
    FirmwareInstallJobManager,
    InstallJobLocked,
    OutputCallback,
)
from loguru import logger
from typedefs import (
    Firmware,
    FlightController,
    FlightControllerFlags,
    FlightControllerV1,
    Parameters,
    Serial,
    SITLFrame,
    TLogMode,
    Vehicle,
)

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = AutoPilotManager()
install_jobs = FirmwareInstallJobManager()


def index_to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    is_async = asyncio.iscoroutinefunction(endpoint)

    @wraps(endpoint)
    async def wrapper(*args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
        try:
            if is_async:
                return await endpoint(*args, **kwargs)
            return endpoint(*args, **kwargs)
        except HTTPException as error:
            raise error
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return wrapper


# By default, all REST resources should have its own router, but as some of them does not implement
# all the CRUD operations, we gonna keep ones that have less than 2 endpoints in the index router.


async def target_board(board_name: Optional[str], board_id: Optional[int] = None) -> FlightController:
    """Returns the board that should be used to perform operations on.

    Most of the API routes that have operations related to board management will give the option to perform those
    operations on the running board or on some of the connected boards. This function abstract this logic that is
    common on all the routes.

    If both `board_name` and `board_id` are None, it will check if there's a running board, and return it if so.
    Otherwise it returns the first connected board, bootloaders included, matching the ArduPilot board id and whose
    platform (case-insensitive) or name matches `board_name`.
    """
    if board_name is None and board_id is None:
        if autopilot.current_board is None:
            raise RuntimeError("No board running and no target board set.")
        return autopilot.current_board

    for board in await autopilot.available_boards(True):
        if board_id is not None and board.ardupilot_board_id != board_id:
            continue
        if board_name is not None and board_name.lower() != board.platform.name.lower() and board_name != board.name:
            continue
        return board
    raise ValueError("Chosen board not available.")


def raise_lock(*raise_args: str, **kwargs: int) -> NoReturn:
    """Raise a 423 HTTP Error status

    Raises:
        HTTPException: Exception that the operation is already in progress.
    """
    raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Operation already in progress.")


async def install_target_board(board_name: Optional[str]) -> FlightController:
    try:
        return await target_board(board_name)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@contextmanager
def install_job_slot() -> Iterator[None]:
    """Hold the single firmware install slot while a request is validated, mapping validation errors to HTTP codes.

    Errors not handled here end up as 500 through index_to_http_exception.
    """
    try:
        with install_jobs.reserve():
            yield
    except InstallJobLocked:
        raise_lock()
    except NoDefaultFirmwareAvailable as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidFirmwareFile as error:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)) from error


def stream_install_job(job: FirmwareInstallJob) -> StreamingResponse:
    """Stream the job log as NDJSON, from its start until its final control line."""

    async def generate() -> AsyncGenerator[str, None]:
        async for stream, line in job.follow():
            yield json.dumps({"stream": stream, "data": line}) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Content-Type": "application/x-ndjson",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        },
    )


@index_router_v1.put("/serials", status_code=status.HTTP_200_OK)
@index_to_http_exception
def update_serials(serials: List[Serial] = Body(...)) -> Any:
    autopilot.update_serials(serials)


@index_router_v1.get("/serials", response_model=List[Serial])
@index_to_http_exception
def get_serials() -> Any:
    return autopilot.get_serials()


@index_router_v1.get("/firmware_info", response_model=FirmwareInfo, summary="Get version and type of current firmware.")
@index_to_http_exception
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
@index_to_http_exception
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
@index_to_http_exception
async def set_sitl_frame(frame: SITLFrame) -> Any:
    return autopilot.set_sitl_frame(frame)


@index_router_v1.get("/sitl_frame", response_model=SITLFrame, summary="Get current SITL Frame type.")
@index_to_http_exception
async def get_sitl_frame() -> Any:
    return autopilot.current_sitl_frame


@index_router_v1.get("/firmware_vehicle_type", response_model=str, summary="Get firmware vehicle type.")
@index_to_http_exception
async def get_firmware_vehicle_type() -> Any:
    if not autopilot.current_board:
        raise RuntimeError("Cannot fetch vehicle type info as there's no board running.")
    return await autopilot.vehicle_manager.get_firmware_vehicle_type()


@index_router_v1.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@index_to_http_exception
async def get_available_firmwares(
    vehicle: Vehicle,
    board_name: Optional[str] = None,
    board_id: Optional[int] = None,
) -> Any:
    """List the firmwares available for the board.

    The platform of the first firmware is the backend's preferred platform for the board, the one it would install
    by itself. Other platforms built for the same board id (variants like "-bdshot") follow it.
    """
    return await autopilot.get_available_firmwares(vehicle, await target_board(board_name, board_id))


@index_router_v1.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@index_to_http_exception
async def install_firmware_from_url(
    url: str,
    board_name: Optional[str] = None,
    make_default: bool = False,
    parameters: Optional[Parameters] = None,
    auto_switch_board: bool = True,
) -> Any:
    with install_job_slot():
        board = await install_target_board(board_name)

        async def switch_board(output_callback: OutputCallback) -> None:
            current = autopilot.current_board
            if not auto_switch_board or current is None or FlightControllerFlags.is_bootloader in board.flags:
                return
            # The flashed build can rename the board it runs on (e.g. "MatekH743" -> "MatekH743-bdshot"), the
            # restart already picked it up under its new name
            if is_same_hardware(board, current):
                autopilot.set_preferred_board(current)
                return
            # In some cases user might install a firmware that implies in a board change but this is not reflected,
            # so if the board is different from the current one, we change it.
            if current.name != board.name:
                # Switch to the board as detected after the flash, which may have been renamed by the new build
                detected_boards = await autopilot.available_boards()
                target = next(
                    (detected for detected in detected_boards if board_matches_preferred(board, detected)),
                    next((detected for detected in detected_boards if is_same_hardware(board, detected)), board),
                )
                await autopilot.change_board(target)
                await output_callback("stdout", f"Switched to board {target.name}")

        job = install_jobs.start(
            partial(autopilot.install_firmware_from_url, url, board, make_default, parameters),
            post_success_steps=[switch_board],
        )
    return stream_install_job(job)


@index_router_v1.post("/install_firmware_from_file", summary="Install firmware from user file.")
@index_to_http_exception
async def install_firmware_from_file(
    binary: UploadFile = File(...),
    board_name: Optional[str] = None,
    parameters: Optional[Parameters] = None,
) -> Any:
    with install_job_slot():
        custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")

        async def remove_custom_firmware(output_callback: OutputCallback) -> None:
            custom_firmware.unlink(missing_ok=True)
            await output_callback("stdout", "Cleaned up temporary firmware file")

        try:
            try:
                with open(custom_firmware, "wb") as buffer:
                    shutil.copyfileobj(binary.file, buffer)
            finally:
                binary.file.close()

            board = await install_target_board(board_name)
            autopilot.firmware_manager.validate_firmware(custom_firmware, board)
            job = install_jobs.start(
                partial(autopilot.install_firmware_from_file, custom_firmware, board, parameters),
                cleanup_steps=[remove_custom_firmware],
            )
        except BaseException:
            custom_firmware.unlink(missing_ok=True)
            raise
    return stream_install_job(job)


@index_router_v1.get(
    "/board", response_model=Optional[FlightControllerV1], summary="Check what is the current running board."
)
@index_to_http_exception
def get_board() -> Any:
    if autopilot.current_board is None:
        return None
    return FlightControllerV1.from_flight_controller(autopilot.current_board)


@index_router_v1.post("/board", summary="Set board to be used.")
@index_to_http_exception
async def set_board(board: FlightController, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> Any:
    autopilot.current_sitl_frame = sitl_frame
    await autopilot.change_board(board)


@index_router_v1.post("/restart", summary="Restart the autopilot with current set options.")
@index_to_http_exception
async def restart() -> Any:
    logger.debug("Restarting ardupilot...")
    await autopilot.restart_ardupilot()
    logger.debug("Ardupilot successfully restarted.")


@index_router_v1.post("/start", summary="Start the autopilot.")
@index_to_http_exception
async def start() -> Any:
    logger.debug("Starting ardupilot...")
    autopilot.set_start_on_boot(True)
    await autopilot.start_ardupilot()
    logger.debug("Ardupilot successfully started.")


@index_router_v1.post("/preferred_router", summary="Set the preferred MAVLink router.")
@index_to_http_exception
async def set_preferred_router(router: str, tlog_mode: Optional[TLogMode] = None) -> Any:
    logger.debug("Setting preferred Router")
    await autopilot.set_preferred_router(router, tlog_mode)
    logger.debug(f"Preferred Router successfully set to {router}")


@index_router_v1.get("/preferred_router", summary="Retrieve preferred router")
@index_to_http_exception
def preferred_router() -> Any:
    return autopilot.load_preferred_router()


@index_router_v1.get("/tlog_mode", response_model=Optional[TLogMode], summary="Retrieve tlog mode")
@index_to_http_exception
def get_tlog_mode() -> Any:
    if not autopilot.mavlink_manager.supports_tlog():
        return None
    return autopilot.load_tlog_mode()


@index_router_v1.get("/available_routers", summary="Retrieve preferred router")
@index_to_http_exception
def available_routers() -> Any:
    return autopilot.get_available_routers()


@index_router_v1.post("/stop", summary="Stop the autopilot.")
@index_to_http_exception
async def stop() -> Any:
    logger.debug("Stopping ardupilot...")
    autopilot.set_start_on_boot(False)
    await autopilot.kill_ardupilot()
    logger.debug("Ardupilot successfully stopped.")


@index_router_v1.post("/restore_default_firmware", summary="Restore default firmware.")
@index_to_http_exception
async def restore_default_firmware(board_name: Optional[str] = None) -> Any:
    with install_job_slot():
        board = await install_target_board(board_name)
        if not autopilot.firmware_manager.is_default_firmware_available(board.platform):
            raise NoDefaultFirmwareAvailable(f"Default firmware not available for '{board.name}'.")
        job = install_jobs.start(partial(autopilot.restore_default_firmware, board))
    return stream_install_job(job)


@index_router_v1.get("/install_firmware_progress", summary="Follow the firmware install currently running.")
@index_to_http_exception
async def install_firmware_progress() -> Any:
    """Stream the log of the running firmware install from its start, ending with its final control line.

    Finished installs are not replayed, so a client never mistakes an old result for a live install.
    """
    job = install_jobs.running_job
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No firmware install running.")
    return stream_install_job(job)


@index_router_v1.get(
    "/available_boards", response_model=List[FlightControllerV1], summary="Retrieve list of connected boards."
)
@index_to_http_exception
async def available_boards() -> Any:
    return [FlightControllerV1.from_flight_controller(board) for board in await autopilot.available_boards(True)]


@index_router_v1.post("/system_id", summary="Set the vehicle's system id.")
@index_to_http_exception
async def set_system_id(value: int = Query(ge=1, le=255)) -> Any:
    if not autopilot.current_board:
        message = "No board running, system ID is unavailable"
        logger.warning(message)
        return PlainTextResponse(message, status_code=503)

    await autopilot.vehicle_manager.set_system_id(value)
