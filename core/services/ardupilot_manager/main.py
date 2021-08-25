#! /usr/bin/env python3
import argparse
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Set

import uvicorn
from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler
from fastapi import Body, FastAPI, File, Response, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
from firmware.FirmwareDownload import Firmware, Platform, Vehicle
from mavlink_proxy.Endpoint import Endpoint

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")

parser = argparse.ArgumentParser(description="ArduPilot Manager service for Blue Robotics Companion")
parser.add_argument("-s", "--sitl", help="run SITL instead of connecting any board", action="store_true")

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)


app = FastAPI(
    title="ArduPilot Manager API",
    description="ArduPilot Manager is responsible for managing ArduPilot devices connected to Companion.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
logger.info("Starting ArduPilot Manager.")
autopilot = ArduPilotManager()


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
def create_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.add_new_endpoints(endpoints)
        autopilot.reload_endpoints()
    except ValueError as error:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": f"{error}"}


@app.delete("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def remove_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.remove_endpoints(endpoints)
        autopilot.reload_endpoints()
    except ValueError as error:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": f"{error}"}


@app.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@version(1, 0)
def get_available_firmwares(response: Response, vehicle: Vehicle) -> Any:
    try:
        return autopilot.get_available_firmwares(vehicle)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@version(1, 0)
def install_firmware_from_url(response: Response, url: str) -> Any:
    try:
        autopilot.kill_ardupilot()
        autopilot.install_firmware_from_url(url)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        autopilot.start_ardupilot()


@app.post("/install_firmware_from_file", summary="Install firmware from user file.")
@version(1, 0)
def install_firmware_from_file(response: Response, binary: UploadFile = File(...)) -> Any:
    custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
    try:
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
        autopilot.kill_ardupilot()
        autopilot.install_firmware_from_file(custom_firmware)
    except InvalidFirmwareFile as error:
        response.status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        return {"message": f"Cannot use this file: {error}"}
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        binary.file.close()
        autopilot.start_ardupilot()


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":
    if args.sitl:
        autopilot.current_platform = Platform.SITL
    autopilot.start_ardupilot()
    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
