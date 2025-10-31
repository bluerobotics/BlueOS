import asyncio
import json
import os
import shutil
from functools import wraps
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, List, Optional, Tuple, Awaitable

from commonwealth.mavlink_comm.exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)
from commonwealth.mavlink_comm.typedefs import FirmwareInfo, MavlinkVehicleType
from commonwealth.utils.decorators import single_threaded
from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi_versioning import versioned_api_route
from loguru import logger

from autopilot_manager import AutoPilotManager
from exceptions import InvalidFirmwareFile, NoDefaultFirmwareAvailable
from typedefs import (
    Firmware,
    FlightController,
    FlightControllerFlags,
    FlightControllerV1,
    Parameters,
    Serial,
    SITLFrame,
    Vehicle,
)

index_router_v1 = APIRouter(
    tags=["index_v1"],
    route_class=versioned_api_route(1, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

autopilot = AutoPilotManager()


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

    If the `board_name` argument is None, it will check if there's a running board, and return it if so. If one
    provides the `board_name`, this function will check if there's a connected board with that name and return it if so.
    """
    if board_name is not None:
        try:
            if board_id is not None:
                return next(
                    board for board in await autopilot.available_boards(True) if board.ardupilot_board_id == board_id
                )
            return next(board for board in await autopilot.available_boards(True) if board.platform.name == board_name)
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


async def streaming_firmware_operation(
    operation_func: Callable[..., Awaitable[None]],
    *operation_args: Any,
    pre_install_callback: Optional[Callable[[asyncio.Queue[Tuple[str, str]]], Awaitable[None]]] = None,
    post_install_callback: Optional[Callable[[asyncio.Queue[Tuple[str, str]]], Awaitable[None]]] = None,
    **operation_kwargs: Any,
) -> StreamingResponse:
    """Common helper for streaming firmware installation operations.

    Args:
        operation_func: The autopilot operation to perform (e.g., autopilot.install_firmware_from_url)
        *operation_args: Positional arguments to pass to the operation function
        pre_install_callback: Optional callback to run before stopping autopilot
        post_install_callback: Optional callback to run after starting autopilot
        **operation_kwargs: Keyword arguments to pass to the operation function
    """

    async def generate() -> AsyncGenerator[str, None]:
        # Create a queue to receive output from the callback
        output_queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()

        async def output_callback(stream: str, line: str) -> None:
            await output_queue.put((stream, line))

        # Start the operation in a separate task
        async def operation_task() -> None:
            try:
                # Run pre-install callback if provided
                if pre_install_callback:
                    await pre_install_callback(output_queue)

                await autopilot.kill_ardupilot()
                await output_queue.put(("stdout", "Stopped autopilot"))

                # Execute the main operation with output callback
                await operation_func(*operation_args, output_callback=output_callback, **operation_kwargs)

            except (InvalidFirmwareFile, NoDefaultFirmwareAvailable, ValueError) as error:
                await output_queue.put(("stderr", f"Error: {str(error)}"))
            except Exception as e:
                await output_queue.put(("stderr", f"Error: {str(e)}"))
            finally:
                await autopilot.start_ardupilot()
                await output_queue.put(("stdout", "Started autopilot"))

                # Run post-install callback if provided
                if post_install_callback:
                    await post_install_callback(output_queue)

                # Signal completion
                await output_queue.put(("done", ""))

        # Start the operation task
        task = asyncio.create_task(operation_task())

        # Stream output as it comes
        try:
            while True:
                stream, line = await output_queue.get()
                if stream == "done":
                    break
                yield json.dumps({"stream": stream, "data": line}) + "\n"
        finally:
            # Ensure task is cleaned up
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

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
    firmware: Optional[str] = "Ardupilot",
) -> Any:
    return autopilot.get_available_firmwares(vehicle, await target_board(board_name, board_id), firmware)


@index_router_v1.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@single_threaded(callback=raise_lock)
async def install_firmware_from_url(
    url: str,
    board_name: Optional[str] = None,
    make_default: bool = False,
    parameters: Optional[Parameters] = None,
    auto_switch_board: bool = True,
) -> Any:
    board = await target_board(board_name)

    async def post_install_callback(output_queue: asyncio.Queue[Tuple[str, str]]) -> None:
        # In some cases user might install a firmware that implies in a board change but this is not reflected,
        # so if the board is different from the current one, we change it.
        if (
            auto_switch_board
            and board
            and autopilot.current_board
            and autopilot.current_board.name != board.name
            and FlightControllerFlags.is_bootloader not in board.flags
        ):
            await autopilot.change_board(board)
            await output_queue.put(("stdout", f"Switched to board {board.name}"))

    return await streaming_firmware_operation(
        autopilot.install_firmware_from_url,
        url,
        board,
        make_default,
        parameters,
        post_install_callback=post_install_callback,
    )


@index_router_v1.post("/install_firmware_from_file", summary="Install firmware from user file.")
@single_threaded(callback=raise_lock)
async def install_firmware_from_file(
    binary: UploadFile = File(...),
    board_name: Optional[str] = None,
    parameters: Optional[Parameters] = None,
) -> Any:
    # Save uploaded file to temporary location
    custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
    try:
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
    finally:
        binary.file.close()

    board = await target_board(board_name)

    async def pre_install_callback(output_queue: asyncio.Queue[Tuple[str, str]]) -> None:
        await output_queue.put(("stdout", "Firmware file uploaded"))

    async def post_install_callback(output_queue: asyncio.Queue[Tuple[str, str]]) -> None:
        if custom_firmware and os.path.exists(custom_firmware):
            os.remove(custom_firmware)
            await output_queue.put(("stdout", "Cleaned up temporary firmware file"))

    return await streaming_firmware_operation(
        autopilot.install_firmware_from_file,
        custom_firmware,
        board,
        parameters,
        pre_install_callback=pre_install_callback,
        post_install_callback=post_install_callback,
    )


@index_router_v1.get(
    "/board", response_model=Optional[FlightControllerV1], summary="Check what is the current running board."
)
@index_to_http_exception
def get_board() -> Any:
    if autopilot.current_board is None:
        return None
    return {
        "name": autopilot.current_board.name,
        "manufacturer": autopilot.current_board.manufacturer,
        "platform": autopilot.current_board.platform.name,
        "platform_type": autopilot.current_board.platform.platform_type.value,
        "ardupilot_board_id": autopilot.current_board.ardupilot_board_id,
        "flags": autopilot.current_board.flags,
    }


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
    await autopilot.start_ardupilot()
    logger.debug("Ardupilot successfully started.")


@index_router_v1.post("/preferred_router", summary="Set the preferred MAVLink router.")
@index_to_http_exception
async def set_preferred_router(router: str) -> Any:
    logger.debug("Setting preferred Router")
    await autopilot.set_preferred_router(router)
    logger.debug(f"Preferred Router successfully set to {router}")


@index_router_v1.get("/preferred_router", summary="Retrieve preferred router")
@index_to_http_exception
def preferred_router() -> Any:
    return autopilot.load_preferred_router()


@index_router_v1.get("/available_routers", summary="Retrieve preferred router")
@index_to_http_exception
def available_routers() -> Any:
    return autopilot.get_available_routers()


@index_router_v1.post("/stop", summary="Stop the autopilot.")
@index_to_http_exception
async def stop() -> Any:
    logger.debug("Stopping ardupilot...")
    await autopilot.kill_ardupilot()
    logger.debug("Ardupilot successfully stopped.")


@index_router_v1.post("/restore_default_firmware", summary="Restore default firmware.")
@single_threaded(callback=raise_lock)
async def restore_default_firmware(board_name: Optional[str] = None) -> Any:
    board = await target_board(board_name)
    return await streaming_firmware_operation(
        autopilot.restore_default_firmware,
        board,
    )


@index_router_v1.get(
    "/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards."
)
@index_to_http_exception
async def available_boards() -> Any:
    return await autopilot.available_boards(True)
